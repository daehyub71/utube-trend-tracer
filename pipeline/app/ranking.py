"""4개 보드 랭킹 산출 (FR-2~5).

보드별 차이는 세 가지뿐이다 — 무엇을 재는가(Δ조회수/Δ구독자), α, 그리고 필터.
같은 산식에 파라미터만 달리해 구현한다 (SPEC FR-7).

수집 공백이 있어도 계산이 멈추지 않도록, 구간 안에서 가장 이른 스냅샷과
최신 스냅샷을 골라 Δ를 잰다 (NFR-7).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.scoring import (
    ALPHA_RISING,
    ALPHA_TRENDING,
    Snapshot,
    score_channel,
    score_video,
)

# 산출 구간 (SPEC FR-7)
VIDEO_WINDOW_HOURS = 48
CHANNEL_WINDOW_HOURS = 24 * 7

# 지금 뜨는 영상은 업로드 7일 이내만 대상 (FR-7)
VIDEO_MAX_AGE_DAYS = 7

# 신규 뜨는 유튜버 구독자 상한 (D7)
RISING_CHANNEL_MAX_SUBSCRIBERS = 100_000


@dataclass(frozen=True)
class VideoSeries:
    """영상 하나의 시계열과 메타.

    Attributes:
        video_id: 영상 id.
        channel_id: 업로드 채널 id.
        category_id: 분류된 카테고리 id.
        subscribers: 채널의 현재 구독자 수.
        is_short: Shorts 여부 (D8).
        published_at: 업로드 시각.
        snapshots: 조회수 스냅샷 목록.
    """

    video_id: str
    channel_id: str
    category_id: str
    subscribers: int
    is_short: bool
    published_at: datetime
    snapshots: list[Snapshot]


@dataclass(frozen=True)
class ChannelSeries:
    """채널 하나의 시계열과 메타.

    Attributes:
        channel_id: 채널 id.
        category_id: 카테고리 id.
        subscribers: 현재 구독자 수.
        snapshots: 측정 대상 스냅샷 (measure에 따라 조회수 또는 구독자).
        measure: `subscribers` 또는 `views`.
    """

    channel_id: str
    category_id: str
    subscribers: int
    snapshots: list[Snapshot]
    measure: str = "subscribers"


@dataclass(frozen=True)
class RankedEntry:
    """랭킹 한 줄.

    Attributes:
        board: 보드 이름.
        category_id: 카테고리 id.
        entity_id: 영상 또는 채널 id.
        score: 산출 점수.
        rank: 카테고리 안에서의 순위 (1부터).
        computed_at: 산출 시각.
        window_start: 사용한 가장 이른 스냅샷 시각.
        window_end: 사용한 최신 스냅샷 시각.
    """

    board: str
    category_id: str
    entity_id: str
    score: float
    rank: int
    computed_at: datetime
    window_start: datetime
    window_end: datetime

    def to_row(self) -> dict[str, Any]:
        """`ut_trend_scores` 테이블에 넣을 dict를 만든다."""
        return {
            "board": self.board,
            "category_id": self.category_id,
            "entity_id": self.entity_id,
            "score": self.score,
            "rank": self.rank,
            "computed_at": self.computed_at.isoformat(),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
        }


def rank_trending_videos(videos: Sequence[VideoSeries], *, now: datetime) -> list[RankedEntry]:
    """지금 뜨는 영상 — Δ조회수, α=0.25, 업로드 7일 이내 (FR-2)."""
    return _rank_videos(videos, now=now, board="trending_videos", alpha=ALPHA_TRENDING)


def rank_rising_videos(videos: Sequence[VideoSeries], *, now: datetime) -> list[RankedEntry]:
    """신규 뜨는 영상 — Δ조회수, α=1.0 (구독자 대비 성과) (FR-3)."""
    return _rank_videos(videos, now=now, board="rising_videos", alpha=ALPHA_RISING)


def rank_trending_channels(channels: Sequence[ChannelSeries], *, now: datetime) -> list[RankedEntry]:
    """지금 뜨는 유튜버 — 주간 성장, α=0.25 (FR-4)."""
    return _rank_channels(channels, now=now, board="trending_channels", alpha=ALPHA_TRENDING)


def rank_rising_channels(channels: Sequence[ChannelSeries], *, now: datetime) -> list[RankedEntry]:
    """신규 뜨는 유튜버 — Δ구독자, α=1.0, 구독자 10만 이하 (FR-5, D7)."""
    eligible = [c for c in channels if c.subscribers <= RISING_CHANNEL_MAX_SUBSCRIBERS]
    return _rank_channels(eligible, now=now, board="rising_channels", alpha=ALPHA_RISING)


def _rank_videos(
    videos: Sequence[VideoSeries], *, now: datetime, board: str, alpha: float
) -> list[RankedEntry]:
    """영상 보드 공통 산출."""
    cutoff = now - timedelta(days=VIDEO_MAX_AGE_DAYS)
    window_start = now - timedelta(hours=VIDEO_WINDOW_HOURS)

    scored: list[tuple[str, str, float, datetime, datetime]] = []
    for item in videos:
        if item.published_at < cutoff:
            continue  # 오래된 영상이 누적 조회수로 눌러앉지 않게 (FR-7)
        pair = _window_pair(item.snapshots, window_start)
        if pair is None:
            continue
        earlier, later = pair
        score = score_video(
            earlier, later, subscribers=item.subscribers, alpha=alpha, is_short=item.is_short
        )
        if score <= 0:
            continue
        scored.append((item.category_id, item.video_id, score, earlier.captured_at, later.captured_at))

    return _assign_ranks(scored, board=board, now=now)


def _rank_channels(
    channels: Sequence[ChannelSeries], *, now: datetime, board: str, alpha: float
) -> list[RankedEntry]:
    """채널 보드 공통 산출."""
    window_start = now - timedelta(hours=CHANNEL_WINDOW_HOURS)

    scored: list[tuple[str, str, float, datetime, datetime]] = []
    for item in channels:
        pair = _window_pair(item.snapshots, window_start)
        if pair is None:
            continue
        earlier, later = pair
        score = score_channel(earlier, later, subscribers=item.subscribers, alpha=alpha)
        if score <= 0:
            continue
        scored.append((item.category_id, item.channel_id, score, earlier.captured_at, later.captured_at))

    return _assign_ranks(scored, board=board, now=now)


def _window_pair(snapshots: Sequence[Snapshot], window_start: datetime) -> tuple[Snapshot, Snapshot] | None:
    """구간 안에서 가장 이른 스냅샷과 최신 스냅샷을 고른다.

    수집 공백이 있어도 남은 두 점으로 계산한다 (NFR-7).
    점이 하나뿐이면 증가량을 알 수 없으므로 None.
    """
    in_window = sorted(
        (s for s in snapshots if s.captured_at >= window_start), key=lambda s: s.captured_at
    )
    if len(in_window) < 2:
        return None
    return in_window[0], in_window[-1]


def _assign_ranks(
    scored: list[tuple[str, str, float, datetime, datetime]], *, board: str, now: datetime
) -> list[RankedEntry]:
    """카테고리별로 점수 내림차순 순위를 매긴다."""
    by_category: dict[str, list[tuple[str, str, float, datetime, datetime]]] = {}
    for entry in scored:
        by_category.setdefault(entry[0], []).append(entry)

    ranked: list[RankedEntry] = []
    for category_id, entries in by_category.items():
        entries.sort(key=lambda e: e[2], reverse=True)
        for position, (_, entity_id, score, start, end) in enumerate(entries, start=1):
            ranked.append(
                RankedEntry(
                    board=board,
                    category_id=category_id,
                    entity_id=entity_id,
                    score=score,
                    rank=position,
                    computed_at=now,
                    window_start=start,
                    window_end=end,
                )
            )

    ranked.sort(key=lambda r: (r.category_id, r.rank))
    return ranked

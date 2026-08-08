"""랭킹 산출 실행 (M3, FR-2~5, FR-7).

DB의 스냅샷 시계열로 4개 보드 랭킹을 계산해 `ut_trend_scores`에 넣는다.
프론트는 이 테이블만 읽으므로, 부분 갱신으로 옛 순위가 섞이지 않게 보드 단위로 교체한다.

스냅샷이 2개 미만인 구간은 계산할 수 없다 — 콜드스타트 초기에는 결과가 비는 것이 정상이다.

사용:
    python -m scripts.run_scoring
    python -m scripts.run_scoring --dry-run   # 계산만 하고 쓰지 않음
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from supabase import create_client

from app.blocklist import load_blocklist
from app.channel_category import resolve_channel_category
from app.config import ConfigError, Settings, ensure_ssl_certificates
from app.ranking import (
    ChannelSeries,
    VideoSeries,
    rank_rising_channels,
    rank_rising_videos,
    rank_trending_channels,
    rank_trending_videos,
)
from app.scoring import Snapshot
from app.store import Store

BOARDS = ("trending_videos", "rising_videos", "trending_channels", "rising_channels")
VIDEO_LOOKBACK_DAYS = 8  # 업로드 7일 이내 + 여유


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="4개 보드 랭킹 산출")
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 결과만 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_ssl_certificates()

    try:
        settings = Settings.from_env(load_dotenv_file=True)
    except ConfigError as exc:
        print(f"설정 오류: {exc}")
        return 1

    now = datetime.now(UTC)
    store = Store(create_client(settings.supabase_url, settings.supabase_service_key))
    blocklist = load_blocklist()

    raw_videos = store.video_series(now - timedelta(days=VIDEO_LOOKBACK_DAYS))
    raw_channels = store.channel_series()
    print(f"영상 {len(raw_videos)}개 · 채널 {len(raw_channels)}개 시계열 조회")

    subscribers = _latest_subscribers(raw_channels)
    videos = _build_video_series(raw_videos, subscribers, blocklist)
    channel_categories = _channel_categories(raw_videos, raw_channels)
    channels_by_subs, channels_by_views = _build_channel_series(
        raw_channels, channel_categories, blocklist
    )

    print(f"산출 대상 — 영상 {len(videos)}개, 채널 {len(channels_by_subs)}개")

    entries = [
        *rank_trending_videos(videos, now=now),
        *rank_rising_videos(videos, now=now),
        # 지금 뜨는 유튜버는 Δ조회수, 신규 뜨는 유튜버는 Δ구독자 (FR-7 표)
        *rank_trending_channels(channels_by_views, now=now),
        *rank_rising_channels(channels_by_subs, now=now),
    ]

    counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        counts[entry.board] += 1
    for board in BOARDS:
        print(f"  {board:20} {counts[board]:>4}건")

    if not entries:
        print("\n산출된 랭킹이 없습니다 — 스냅샷이 2회 이상 쌓여야 증가량을 잴 수 있습니다 (콜드스타트).")

    if args.dry_run:
        print("\ndry-run — DB에 쓰지 않고 종료합니다.")
        return 0

    written = store.replace_trend_scores([e.to_row() for e in entries], boards=BOARDS)
    print(f"\nut_trend_scores 갱신 완료 — {written}건")
    return 0


def _latest_subscribers(raw_channels: list[dict[str, Any]]) -> dict[str, int]:
    """채널별 최신 구독자 수를 뽑는다."""
    result: dict[str, int] = {}
    for channel in raw_channels:
        snaps = channel.get("ut_channel_snapshots") or []
        if not snaps:
            continue
        latest = max(snaps, key=lambda s: str(s["captured_at"]))
        result[str(channel["channel_id"])] = int(latest.get("subscriber_count") or 0)
    return result


def _channel_categories(
    raw_videos: list[dict[str, Any]], raw_channels: list[dict[str, Any]]
) -> dict[str, str | None]:
    """채널의 카테고리를 영상 분포로 정한다 (D9 이월 과제)."""
    by_channel: dict[str, list[str]] = defaultdict(list)
    for video in raw_videos:
        if video.get("unclassified"):
            continue
        for category_id in video.get("category_ids") or []:
            by_channel[str(video["channel_id"])].append(str(category_id))

    resolved: dict[str, str | None] = {}
    for channel in raw_channels:
        channel_id = str(channel["channel_id"])
        seeded = (channel.get("category_ids") or [None])[0]
        # 시드에는 대분류만 들어 있다 (예: 'food') — 태그 없는 값만 fallback으로 쓴다.
        fallback = str(seeded) if seeded and "_" not in str(seeded) else None
        resolved[channel_id] = resolve_channel_category(
            by_channel.get(channel_id, []), fallback_parent=fallback
        )
    return resolved


def _build_video_series(
    raw_videos: list[dict[str, Any]], subscribers: dict[str, int], blocklist: Any
) -> list[VideoSeries]:
    """DB 행을 산출용 시계열로 바꾼다 (차단·연령제한·미분류 제외)."""
    series: list[VideoSeries] = []
    for video in raw_videos:
        if video.get("unclassified") or video.get("age_restricted"):
            continue
        video_id = str(video["video_id"])
        channel_id = str(video["channel_id"])
        if blocklist.is_video_blocked(video_id) or blocklist.is_channel_blocked(channel_id):
            continue
        categories = video.get("category_ids") or []
        if not categories:
            continue
        snaps = _snapshots(video.get("ut_video_snapshots") or [], "view_count")
        if len(snaps) < 2:
            continue
        published = _parse_dt(video.get("published_at"))
        if published is None:
            continue
        series.append(
            VideoSeries(
                video_id=video_id,
                channel_id=channel_id,
                category_id=str(categories[0]),
                subscribers=subscribers.get(channel_id, 0),
                is_short=bool(video.get("is_short")),
                published_at=published,
                snapshots=snaps,
            )
        )
    return series


def _build_channel_series(
    raw_channels: list[dict[str, Any]], categories: dict[str, str | None], blocklist: Any
) -> tuple[list[ChannelSeries], list[ChannelSeries]]:
    """채널 시계열을 측정 대상별로 나눠 만든다.

    '지금 뜨는 유튜버'는 Δ조회수, '신규 뜨는 유튜버'는 Δ구독자를 잰다 (FR-7 표) —
    한 목록에 섞으면 두 보드가 서로의 측정치로도 순위를 매기게 된다.

    Returns:
        (구독자 기준 시계열, 조회수 기준 시계열).
    """
    by_subscribers: list[ChannelSeries] = []
    by_views: list[ChannelSeries] = []

    for channel in raw_channels:
        channel_id = str(channel["channel_id"])
        if blocklist.is_channel_blocked(channel_id):
            continue
        category_id = categories.get(channel_id)
        if not category_id:
            continue

        raw_snaps = channel.get("ut_channel_snapshots") or []
        subs = _snapshots(raw_snaps, "subscriber_count")
        views = _snapshots(raw_snaps, "view_count")
        if len(subs) < 2:
            continue
        current = subs[-1].value

        by_subscribers.append(
            ChannelSeries(
                channel_id=channel_id,
                category_id=category_id,
                subscribers=current,
                snapshots=subs,
                measure="subscribers",
            )
        )
        if len(views) >= 2:
            by_views.append(
                ChannelSeries(
                    channel_id=channel_id,
                    category_id=category_id,
                    subscribers=current,
                    snapshots=views,
                    measure="views",
                )
            )

    return by_subscribers, by_views


def _snapshots(rows: list[dict[str, Any]], field: str) -> list[Snapshot]:
    """스냅샷 행을 시각순 Snapshot 목록으로 바꾼다."""
    points: list[Snapshot] = []
    for row in rows:
        captured = _parse_dt(row.get("captured_at"))
        if captured is None:
            continue
        points.append(Snapshot(captured_at=captured, value=int(row.get(field) or 0)))
    points.sort(key=lambda s: s.captured_at)
    return points


def _parse_dt(value: Any) -> datetime | None:
    """ISO 문자열을 tz 인식 datetime으로 바꾼다."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


if __name__ == "__main__":
    sys.exit(main())

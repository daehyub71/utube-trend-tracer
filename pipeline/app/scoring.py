"""트렌드 지수 산출 (SPEC FR-7, D8).

산식: `score = Δ값 / (Δ시간h × max(구독자, floor)^α)`

α는 보드마다 다르다. "지금 뜨는"은 낮은 α로 절대 규모를 반영하고,
"신규 뜨는"은 α=1.0으로 규모를 중립화해 "구독자 대비 성과"를 만든다.
**α ≥ 1.0 은 규약이다** — α<1이면 신규 보드도 결국 규모 순이 된다
(α=0.7 시연에서 실제로 그랬다). tests/test_scoring_contract.py가 이 관계를 강제한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

# SPEC FR-7 확정값 (2026-08-03 시연으로 교정)
ALPHA_TRENDING = 0.25
ALPHA_RISING = 1.00
SUBSCRIBER_FLOOR = 1_000

# Shorts 보정 계수 (D8) — 초기값이며 콜드스타트 실데이터로 교정한다 (M6).
SHORTS_BETA = 0.5

# Shorts 판별: 영상 길이 ≤ 3분 (D8)
SHORTS_MAX_DURATION_S = 180

TRENDING_BOARDS = ("trending_videos", "trending_channels")
RISING_BOARDS = ("rising_videos", "rising_channels")


@dataclass(frozen=True)
class Snapshot:
    """시계열 스냅샷 한 점.

    Attributes:
        captured_at: 실제 수집 시각 — Δ시간의 기준 (예정 시각이 아니다).
        value: 조회수 또는 구독자 수.
    """

    captured_at: datetime
    value: int


class BoardAlpha:
    """보드별 α 값."""

    @staticmethod
    def for_board(board: str) -> float:
        """보드 이름으로 α를 돌려준다.

        Args:
            board: `trending_videos` / `rising_videos` / `trending_channels` / `rising_channels`.

        Returns:
            해당 보드의 α.

        Raises:
            ValueError: 알 수 없는 보드 이름.
        """
        if board in TRENDING_BOARDS:
            return ALPHA_TRENDING
        if board in RISING_BOARDS:
            return ALPHA_RISING
        raise ValueError(f"알 수 없는 보드: {board}")


def delta_hours(earlier: Snapshot, later: Snapshot) -> float:
    """두 스냅샷 사이의 실제 경과 시간(시간 단위)을 잰다.

    cron이 지연돼도 정확해야 하므로 예정 간격을 쓰지 않는다 (FR-7).
    """
    return (later.captured_at - earlier.captured_at).total_seconds() / 3600.0


def is_short_duration(duration_s: int | None) -> bool:
    """영상 길이로 Shorts 여부를 판별한다 (D8).

    길이를 모르는 영상은 일반 영상으로 본다 — 보정을 함부로 걸지 않는다.
    """
    if not duration_s or duration_s <= 0:
        return False
    return duration_s <= SHORTS_MAX_DURATION_S


def normalized_velocity(*, delta: float, hours: float, subscribers: int, alpha: float) -> float:
    """정규화 velocity 점수를 계산한다 (SPEC FR-7 산식 B).

    Args:
        delta: 구간의 조회수/구독자 증가량.
        hours: 실측 경과 시간.
        subscribers: 채널 구독자 수 (floor 미만은 floor로 본다).
        alpha: 규모 정규화 지수.

    Returns:
        점수. 증가량이 음수이거나 경과 시간이 0 이하면 0.0.
    """
    if delta <= 0 or hours <= 0:
        return 0.0
    scale: float = math.pow(max(subscribers, SUBSCRIBER_FLOOR), alpha)
    return delta / (hours * scale)


def score_video(
    earlier: Snapshot,
    later: Snapshot,
    *,
    subscribers: int,
    alpha: float,
    is_short: bool = False,
) -> float:
    """영상 점수를 계산한다.

    Args:
        earlier: 이전 스냅샷.
        later: 최신 스냅샷.
        subscribers: 업로드 채널의 구독자 수.
        alpha: 보드의 α.
        is_short: Shorts 여부 — True면 β를 곱한다 (D8).

    Returns:
        보정까지 반영된 최종 점수.
    """
    score = normalized_velocity(
        delta=later.value - earlier.value,
        hours=delta_hours(earlier, later),
        subscribers=subscribers,
        alpha=alpha,
    )
    return score * SHORTS_BETA if is_short else score


def score_channel(
    earlier: Snapshot,
    later: Snapshot,
    *,
    subscribers: int,
    alpha: float,
) -> float:
    """채널 점수를 계산한다.

    Shorts 보정은 영상 단위 개념이므로 채널 점수에는 적용하지 않는다.

    Args:
        earlier: 이전 스냅샷.
        later: 최신 스냅샷.
        subscribers: 현재 구독자 수.
        alpha: 보드의 α.

    Returns:
        점수.
    """
    return normalized_velocity(
        delta=later.value - earlier.value,
        hours=delta_hours(earlier, later),
        subscribers=subscribers,
        alpha=alpha,
    )

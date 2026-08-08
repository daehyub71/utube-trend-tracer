"""트렌드 지수 산식의 규약 테스트 (SPEC FR-7).

SPEC이 못 박은 관계를 코드가 지키는지 강제한다.

    score = Δ값 / (Δ시간h × max(구독자, floor)^α)

Δ가 구독자에 비례할 때 `score ∝ 구독자^(1-α)` 이므로,
α<1 이면 "신규 뜨는"도 결국 규모 순이 된다 (α=0.7 시연에서 실제로 그랬다).
α=1.0 에서만 "구독자 대비 성과"라는 정의가 성립한다 — 이 테스트가 그 관계를 지킨다.
"""

import pytest

from app.scoring import (
    ALPHA_RISING,
    ALPHA_TRENDING,
    SUBSCRIBER_FLOOR,
    BoardAlpha,
    normalized_velocity,
)


def test_alpha_constants_match_spec() -> None:
    """SPEC 확정값 (2026-08-03 시연으로 교정)."""
    assert ALPHA_TRENDING == 0.25
    assert ALPHA_RISING == 1.00
    assert SUBSCRIBER_FLOOR == 1_000


def test_rising_boards_require_alpha_at_least_one() -> None:
    """α ≥ 1.0 은 규약이다 — '신규 뜨는' 보드에 α<1 이 들어오면 실패한다."""
    for board in ("rising_videos", "rising_channels"):
        assert BoardAlpha.for_board(board) >= 1.0, f"{board} 의 α 가 1.0 미만이다"


def test_rising_score_is_scale_neutral() -> None:
    """α=1.0 에서 Δ가 구독자에 비례하면 점수가 규모와 무관해진다.

    구독자 1만·10만·100만 채널이 각각 구독자의 10%만큼 조회수를 얻었다면
    셋 다 같은 점수여야 한다 — 이것이 '구독자 대비 성과'의 정의다.
    """
    scores = [
        normalized_velocity(delta=subs * 0.1, hours=24.0, subscribers=subs, alpha=ALPHA_RISING)
        for subs in (10_000, 100_000, 1_000_000)
    ]

    assert scores[0] == pytest.approx(scores[1])
    assert scores[1] == pytest.approx(scores[2])


def test_alpha_below_one_reintroduces_scale_bias() -> None:
    """α<1 이면 규모가 큰 쪽이 이긴다 — 이 성질 때문에 α≥1.0 을 규약으로 둔다.

    실패한 α=0.7 시연을 회귀 테스트로 남긴다.
    """
    small = normalized_velocity(delta=1_000, hours=24.0, subscribers=10_000, alpha=0.7)
    large = normalized_velocity(delta=100_000, hours=24.0, subscribers=1_000_000, alpha=0.7)

    assert large > small, "α<1 에서는 규모가 큰 채널이 이긴다 (그래서 rising에 쓰지 않는다)"


def test_trending_alpha_keeps_partial_scale() -> None:
    """'지금 뜨는'은 α=0.25 로 규모를 반영하되 완만한 핸디캡만 준다."""
    small = normalized_velocity(delta=1_000, hours=24.0, subscribers=10_000, alpha=ALPHA_TRENDING)
    large = normalized_velocity(delta=100_000, hours=24.0, subscribers=1_000_000, alpha=ALPHA_TRENDING)

    assert large > small  # 절대 규모가 반영된다
    assert large / small < 100  # 다만 Δ 비율(100배)보다는 완만하다


def test_floor_prevents_tiny_channel_explosion() -> None:
    """구독자가 floor 미만이면 floor로 계산한다 — 구독자 1명이 점수를 폭발시키지 않게."""
    one_sub = normalized_velocity(delta=1_000, hours=24.0, subscribers=1, alpha=ALPHA_RISING)
    floor_sub = normalized_velocity(
        delta=1_000, hours=24.0, subscribers=SUBSCRIBER_FLOOR, alpha=ALPHA_RISING
    )

    assert one_sub == pytest.approx(floor_sub)


def test_score_scales_inversely_with_elapsed_time() -> None:
    """같은 Δ라도 더 긴 시간에 걸쳐 쌓였으면 점수가 낮다 (속도 지표)."""
    fast = normalized_velocity(delta=10_000, hours=6.0, subscribers=50_000, alpha=ALPHA_TRENDING)
    slow = normalized_velocity(delta=10_000, hours=24.0, subscribers=50_000, alpha=ALPHA_TRENDING)

    assert fast == pytest.approx(slow * 4)


def test_negative_delta_is_zero() -> None:
    """조회수·구독자가 줄어든 구간은 0으로 본다 (음수 랭킹 방지)."""
    assert normalized_velocity(delta=-500, hours=24.0, subscribers=10_000, alpha=1.0) == 0.0


def test_zero_or_negative_hours_is_zero() -> None:
    """Δ시간이 0 이하면 계산하지 않는다 (중복 스냅샷·시계 역행 방어)."""
    assert normalized_velocity(delta=1_000, hours=0.0, subscribers=10_000, alpha=1.0) == 0.0
    assert normalized_velocity(delta=1_000, hours=-3.0, subscribers=10_000, alpha=1.0) == 0.0

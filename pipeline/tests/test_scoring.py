"""트렌드 지수 산출 테스트 (SPEC FR-7, D8).

Δ시간은 예정 시각이 아니라 스냅샷 실측 시각으로 잰다 — cron이 늦어도 점수가 정확해야 한다.
Shorts는 β로 보정한다 (초기 0.5, 콜드스타트 후 실데이터로 교정).
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.scoring import (
    SHORTS_BETA,
    Snapshot,
    delta_hours,
    is_short_duration,
    score_channel,
    score_video,
)

BASE = datetime(2026, 8, 8, 0, 0, tzinfo=UTC)


def snap(hours: float, value: int) -> Snapshot:
    return Snapshot(captured_at=BASE + timedelta(hours=hours), value=value)


class TestDeltaHours:
    def test_measures_actual_elapsed_time(self) -> None:
        """예정 간격이 아니라 실제 시각 차이를 쓴다 (cron 지연 대응)."""
        assert delta_hours(snap(0, 0), snap(8, 0)) == pytest.approx(8.0)

    def test_handles_delayed_cron(self) -> None:
        """cron이 40분 늦게 돌아도 실측값이 나온다."""
        assert delta_hours(snap(0, 0), snap(8.667, 0)) == pytest.approx(8.667, abs=0.01)

    def test_same_instant_is_zero(self) -> None:
        assert delta_hours(snap(3, 0), snap(3, 0)) == 0.0


class TestShortsDetection:
    def test_three_minutes_or_less_is_short(self) -> None:
        """판별 기준은 영상 길이 ≤ 3분 (D8)."""
        assert is_short_duration(60) is True
        assert is_short_duration(180) is True

    def test_longer_than_three_minutes_is_not_short(self) -> None:
        assert is_short_duration(181) is False
        assert is_short_duration(600) is False

    def test_unknown_duration_is_not_short(self) -> None:
        """길이를 못 받은 영상은 일반 영상으로 본다 (보정을 함부로 걸지 않는다)."""
        assert is_short_duration(None) is False
        assert is_short_duration(0) is False


class TestVideoScore:
    def test_applies_shorts_beta(self) -> None:
        """Shorts는 β를 곱한다 — 무보정 시 velocity 랭킹을 도배하기 때문 (D8)."""
        args = dict(subscribers=100_000, alpha=0.25)
        regular = score_video(snap(0, 10_000), snap(24, 110_000), is_short=False, **args)
        short = score_video(snap(0, 10_000), snap(24, 110_000), is_short=True, **args)

        assert short == pytest.approx(regular * SHORTS_BETA)

    def test_beta_initial_value_is_documented(self) -> None:
        """초기값 0.5 — 콜드스타트 실데이터로 교정 예정 (M6)."""
        assert SHORTS_BETA == 0.5

    def test_uses_view_delta_between_snapshots(self) -> None:
        score = score_video(snap(0, 1_000), snap(10, 11_000), subscribers=10_000, alpha=1.0)

        # Δ조회수 10,000 / (10시간 × 10,000구독자^1.0)
        assert score == pytest.approx(10_000 / (10 * 10_000))


class TestChannelScore:
    def test_uses_subscriber_delta_for_rising(self) -> None:
        """신규 뜨는 유튜버는 Δ구독자를 잰다 (SPEC FR-7 표)."""
        score = score_channel(snap(0, 10_000), snap(24 * 7, 20_000), subscribers=10_000, alpha=1.0)

        assert score == pytest.approx(10_000 / (168 * 10_000))

    def test_channel_score_has_no_shorts_beta(self) -> None:
        """채널 점수에는 Shorts 보정이 없다 (영상 단위 개념이다)."""
        score = score_channel(snap(0, 1_000), snap(24, 2_000), subscribers=5_000, alpha=0.25)

        assert score > 0

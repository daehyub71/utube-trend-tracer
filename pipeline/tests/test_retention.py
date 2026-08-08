"""보관 정책·졸업 테스트 (NFR-1, D11, D12).

30일 롤링은 무료 용량 관리이기 이전에 YouTube 약관 요구사항이다.
졸업은 추적 채널이 상한을 넘지 않도록 하는 유일한 장치다.
"""

from datetime import UTC, datetime, timedelta

from app.retention import (
    RETENTION_DAYS,
    TRACKED_CHANNEL_LIMIT,
    graduation_candidates,
    purge_cutoff,
    select_channels_to_graduate,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def channel(
    channel_id: str,
    *,
    days_since_upload: float | None,
    score: float = 0.0,
    is_seed: bool = False,
) -> dict[str, object]:
    last_upload = None if days_since_upload is None else NOW - timedelta(days=days_since_upload)
    return {
        "channel_id": channel_id,
        "last_upload_at": last_upload,
        "recent_score": score,
        "is_seed": is_seed,
    }


class TestPurge:
    def test_cutoff_is_thirty_days(self) -> None:
        """30일 롤링 — 약관 요구사항 (NFR-1)."""
        assert RETENTION_DAYS == 30
        assert purge_cutoff(NOW) == NOW - timedelta(days=30)


class TestGraduationCandidates:
    def test_dormant_channel_is_candidate(self) -> None:
        """30일 무업로드 채널은 졸업 후보 (D11)."""
        candidates = graduation_candidates([channel("UCa", days_since_upload=45)], now=NOW)

        assert [c["channel_id"] for c in candidates] == ["UCa"]

    def test_active_channel_is_not_candidate(self) -> None:
        candidates = graduation_candidates([channel("UCa", days_since_upload=3)], now=NOW)

        assert candidates == []

    def test_channel_without_upload_record_is_candidate(self) -> None:
        """업로드 기록이 없는 채널도 후보다 (수집 낭비)."""
        candidates = graduation_candidates([channel("UCa", days_since_upload=None)], now=NOW)

        assert [c["channel_id"] for c in candidates] == ["UCa"]

    def test_seed_channels_are_protected(self) -> None:
        """수동 시드는 자동 졸업시키지 않는다 — 운영자가 고른 채널이다."""
        candidates = graduation_candidates(
            [channel("UCseed", days_since_upload=90, is_seed=True)], now=NOW
        )

        assert candidates == []


class TestSelectChannelsToGraduate:
    def test_under_limit_graduates_only_dormant(self) -> None:
        """상한에 여유가 있으면 휴면 채널만 정리한다."""
        channels = [
            channel("dormant", days_since_upload=60),
            channel("active", days_since_upload=1, score=0.001),
        ]

        selected = select_channels_to_graduate(channels, now=NOW, limit=100)

        assert [c["channel_id"] for c in selected] == ["dormant"]

    def test_over_limit_graduates_lowest_scoring(self) -> None:
        """상한을 넘으면 성과 하위부터 추가로 졸업시킨다 (D11)."""
        channels = [
            channel(f"UC{i}", days_since_upload=1, score=float(i)) for i in range(5)
        ]

        selected = select_channels_to_graduate(channels, now=NOW, limit=3)

        # 5개 중 3개만 남겨야 하므로 점수 하위 2개(0, 1)가 졸업한다.
        assert {c["channel_id"] for c in selected} == {"UC0", "UC1"}

    def test_seeds_survive_limit_pressure(self) -> None:
        """상한 압박에서도 시드는 남는다."""
        channels = [
            channel("seed_low", days_since_upload=1, score=0.0, is_seed=True),
            channel("normal_high", days_since_upload=1, score=9.0),
            channel("normal_low", days_since_upload=1, score=1.0),
        ]

        selected = select_channels_to_graduate(channels, now=NOW, limit=2)

        assert [c["channel_id"] for c in selected] == ["normal_low"]

    def test_default_limit_matches_spec(self) -> None:
        """추적 채널 상한 2,000개 (D11)."""
        assert TRACKED_CHANNEL_LIMIT == 2_000

    def test_no_graduation_when_all_active_and_under_limit(self) -> None:
        channels = [channel(f"UC{i}", days_since_upload=1, score=1.0) for i in range(3)]

        assert select_channels_to_graduate(channels, now=NOW, limit=10) == []

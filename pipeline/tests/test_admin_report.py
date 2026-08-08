"""운영 리포트 렌더링 테스트 (FR-9, NFR-10, D13).

리포트는 public 리포에 커밋되므로 (D13) 키·연락처가 섞이면 안 된다 (NFR-10).
"""

from datetime import UTC, datetime, timedelta

from app.admin_checks import OpsStats, run_checks
from app.admin_report import render_report

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def stats(**overrides: object) -> OpsStats:
    base = OpsStats(
        categories=12,
        seed_counts={"food": 17, "travel": 17},
        tracked_channels=98,
        last_collect_at=NOW - timedelta(hours=2),
        quota_used_today=120,
        unclassified_rate=0.138,
        ranked_categories=1,
        rss_pass_rate=1.0,
        last_rss_verified_at=NOW - timedelta(days=1),
        oldest_snapshot_at=NOW - timedelta(days=3),
        video_snapshot_rows=318,
    )
    return OpsStats(**{**base.__dict__, **overrides})


def render(**overrides: object) -> str:
    current = stats(**overrides)
    return render_report(current, run_checks(current, now=NOW), now=NOW)


class TestStructure:
    def test_includes_generated_time(self) -> None:
        assert "2026-08-08" in render()

    def test_includes_every_check(self) -> None:
        report = render()

        for title in ["시드 커버리지", "수집 신선도", "쿼터 사용량", "미분류율", "추적 채널 수"]:
            assert title in report

    def test_includes_key_metrics(self) -> None:
        report = render()

        assert "98" in report  # 추적 채널
        assert "318" in report  # 스냅샷 행

    def test_summary_shows_worst_level_first(self) -> None:
        """가장 심각한 상태가 맨 위에 와야 한 눈에 보인다."""
        report = render(last_collect_at=None)

        head = report.split("##")[0]
        assert "조치 필요" in head


class TestSecrecy:
    def test_does_not_leak_keys_or_contact(self) -> None:
        """public 리포에 커밋되는 산출물이다 (NFR-10, D13)."""
        report = render()

        for forbidden in ["SUPABASE_SERVICE_KEY", "YOUTUBE_API_KEY", "eyJ", "@gmail.com", "supabase.co"]:
            assert forbidden not in report

    def test_does_not_include_channel_ids(self) -> None:
        """쿼터·시드 수는 공개해도 되지만 (D13) 리포트에 원문 식별자를 늘어놓지는 않는다."""
        report = render()

        assert "UC" not in report


class TestDegradedState:
    def test_unavailable_metric_is_marked(self) -> None:
        """조회 불가 항목이 정상처럼 보이면 안 된다 (NFR-9)."""
        report = render(quota_used_today=None)

        assert "조회 불가" in report

    def test_other_sections_still_render(self) -> None:
        report = render(tracked_channels=None)

        assert "수집 신선도" in report
        assert "미분류율" in report

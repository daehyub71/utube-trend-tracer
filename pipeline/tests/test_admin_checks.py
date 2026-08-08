"""운영 콘솔 자동 점검 테스트 (FR-9, NFR-9).

상황판이 장애와 함께 죽으면 쓸모가 없다 — 조회에 실패한 항목은 '조회 불가'로
표시하되 나머지 점검은 그대로 수행해야 한다.
"""

from datetime import UTC, datetime, timedelta

from app.admin_checks import Level, OpsStats, run_checks

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def healthy(**overrides: object) -> OpsStats:
    """모든 지표가 정상인 기준 상태."""
    base = OpsStats(
        categories=12,
        seed_counts={"food": 17, "travel": 17, "tech": 17, "aicoding": 13, "vlog": 17, "fitness": 17},
        tracked_channels=98,
        last_collect_at=NOW - timedelta(hours=3),
        quota_used_today=120,
        quota_limit=10_000,
        unclassified_rate=0.138,
        ranked_categories=12,
        rss_pass_rate=1.0,
        last_rss_verified_at=NOW - timedelta(days=1),
        oldest_snapshot_at=NOW - timedelta(days=12),
        video_snapshot_rows=54_000,
    )
    return OpsStats(**{**base.__dict__, **overrides})


def find(checks: list, key: str):
    return next(c for c in checks if c.key == key)


class TestHealthyState:
    def test_all_checks_pass(self) -> None:
        checks = run_checks(healthy(), now=NOW)

        assert all(c.level is Level.OK for c in checks), [c.key for c in checks if c.level is not Level.OK]

    def test_every_check_is_reported(self) -> None:
        """점검 항목이 빠지면 문제를 못 본다 — 개수를 고정한다 (FR-9)."""
        checks = run_checks(healthy(), now=NOW)

        assert {c.key for c in checks} == {
            "seed_coverage",
            "rss_pass_rate",
            "rss_verification_age",
            "collect_freshness",
            "retention",
            "ranking_coverage",
            "quota",
            "unclassified_rate",
            "channel_limit",
        }


class TestSeedCoverage:
    def test_empty_category_is_critical(self) -> None:
        """시드가 없는 카테고리는 영원히 빈 보드가 된다."""
        check = find(run_checks(healthy(seed_counts={"food": 17, "travel": 0}), now=NOW), "seed_coverage")

        assert check.level is Level.CRITICAL
        assert "travel" in check.detail

    def test_thin_category_warns(self) -> None:
        """10개 미만이면 D4 기준(10~20개)에 못 미친다."""
        check = find(run_checks(healthy(seed_counts={"food": 5}), now=NOW), "seed_coverage")

        assert check.level is Level.WARN


class TestCollectFreshness:
    def test_stale_collection_is_critical(self) -> None:
        """12시간 넘게 수집이 없으면 cron이 멈춘 것이다 (FR-9)."""
        stale = healthy(last_collect_at=NOW - timedelta(hours=13))
        check = find(run_checks(stale, now=NOW), "collect_freshness")

        assert check.level is Level.CRITICAL

    def test_never_collected_is_critical(self) -> None:
        check = find(run_checks(healthy(last_collect_at=None), now=NOW), "collect_freshness")

        assert check.level is Level.CRITICAL


class TestQuota:
    def test_near_limit_warns(self) -> None:
        """80% 넘으면 남은 주기의 수집이 잘릴 수 있다 (NFR-4)."""
        check = find(run_checks(healthy(quota_used_today=8_500), now=NOW), "quota")

        assert check.level is Level.WARN

    def test_exhausted_is_critical(self) -> None:
        check = find(run_checks(healthy(quota_used_today=10_000), now=NOW), "quota")

        assert check.level is Level.CRITICAL


class TestRetention:
    def test_rows_older_than_thirty_days_is_critical(self) -> None:
        """보관 정책 위반은 약관 위반이다 (NFR-1)."""
        check = find(run_checks(healthy(oldest_snapshot_at=NOW - timedelta(days=31)), now=NOW), "retention")

        assert check.level is Level.CRITICAL


class TestUnclassifiedRate:
    def test_above_threshold_warns_with_llm_trigger(self) -> None:
        """30% 초과가 2주 지속되면 LLM 분류 검토 대상이다 (D10)."""
        check = find(run_checks(healthy(unclassified_rate=0.35), now=NOW), "unclassified_rate")

        assert check.level is Level.WARN
        assert "LLM" in check.detail

    def test_below_threshold_is_ok(self) -> None:
        check = find(run_checks(healthy(unclassified_rate=0.29), now=NOW), "unclassified_rate")

        assert check.level is Level.OK


class TestChannelLimit:
    def test_near_limit_warns(self) -> None:
        """상한(2,000)의 90%에 닿으면 졸업이 신규 편입을 막기 시작한다 (D11)."""
        check = find(run_checks(healthy(tracked_channels=1_850), now=NOW), "channel_limit")

        assert check.level is Level.WARN

    def test_over_limit_is_critical(self) -> None:
        check = find(run_checks(healthy(tracked_channels=2_100), now=NOW), "channel_limit")

        assert check.level is Level.CRITICAL


class TestRankingCoverage:
    def test_no_rankings_warns_during_cold_start(self) -> None:
        """콜드스타트에는 랭킹이 비는 것이 정상이므로 경고까지만 올린다."""
        check = find(run_checks(healthy(ranked_categories=0), now=NOW), "ranking_coverage")

        assert check.level is Level.WARN


class TestRssChecks:
    def test_low_pass_rate_warns(self) -> None:
        check = find(run_checks(healthy(rss_pass_rate=0.8), now=NOW), "rss_pass_rate")

        assert check.level is Level.WARN

    def test_stale_verification_warns(self) -> None:
        """검증 기록이 노후되면 통과율 수치를 믿을 수 없다."""
        check = find(
            run_checks(healthy(last_rss_verified_at=NOW - timedelta(days=10)), now=NOW),
            "rss_verification_age",
        )

        assert check.level is Level.WARN


class TestUnavailableData:
    def test_missing_metric_is_unknown_not_ok(self) -> None:
        """조회 실패를 '정상'으로 표시하면 장애를 놓친다 (NFR-9)."""
        check = find(run_checks(healthy(quota_used_today=None), now=NOW), "quota")

        assert check.level is Level.UNKNOWN
        assert "조회 불가" in check.detail

    def test_other_checks_still_run_when_one_is_unavailable(self) -> None:
        """한 항목이 조회 불가여도 나머지는 그대로 점검한다 (NFR-9)."""
        checks = run_checks(healthy(tracked_channels=None, seed_counts=None), now=NOW)

        assert find(checks, "channel_limit").level is Level.UNKNOWN
        assert find(checks, "seed_coverage").level is Level.UNKNOWN
        assert find(checks, "quota").level is Level.OK
        assert find(checks, "collect_freshness").level is Level.OK

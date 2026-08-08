"""운영 콘솔 자동 점검 (FR-9, NFR-9).

각 점검은 순수 함수다 — 통계를 받아 상태만 돌려준다. DB 조회에 실패한 지표는
None으로 들어오고 UNKNOWN('조회 불가')으로 표시된다. 조회 실패를 정상으로
표시하면 장애를 놓치고, 예외로 던지면 상황판이 장애와 함께 죽는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.quota import DAILY_QUOTA_LIMIT
from app.retention import RETENTION_DAYS, TRACKED_CHANNEL_LIMIT

# 임계값
COLLECT_STALE_HOURS = 12
QUOTA_WARN_RATIO = 0.8
SEED_MIN_PER_CATEGORY = 10  # D4: 카테고리당 10~20개
UNCLASSIFIED_WARN_RATE = 0.30  # D10: 초과가 2주 지속되면 LLM 분류 검토
CHANNEL_LIMIT_WARN_RATIO = 0.9
RSS_PASS_WARN_RATE = 0.9
RSS_VERIFY_STALE_DAYS = 7


class Level(Enum):
    """점검 결과 등급."""

    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Check:
    """점검 한 항목.

    Attributes:
        key: 항목 식별자.
        title: 표시용 이름.
        level: 결과 등급.
        detail: 사람이 읽을 설명 — 무엇이 문제이고 무엇을 해야 하는지.
    """

    key: str
    title: str
    level: Level
    detail: str


@dataclass
class OpsStats:
    """상황판이 쓰는 지표 묶음.

    조회에 실패한 항목은 None으로 둔다 (NFR-9).
    """

    categories: int | None = None
    seed_counts: dict[str, int] | None = None
    tracked_channels: int | None = None
    last_collect_at: datetime | None = None
    quota_used_today: int | None = None
    quota_limit: int = DAILY_QUOTA_LIMIT
    unclassified_rate: float | None = None
    ranked_categories: int | None = None
    rss_pass_rate: float | None = None
    last_rss_verified_at: datetime | None = None
    oldest_snapshot_at: datetime | None = None
    video_snapshot_rows: int | None = None
    unavailable: list[str] = field(default_factory=list)


def run_checks(stats: OpsStats, *, now: datetime) -> list[Check]:
    """모든 자동 점검을 수행한다.

    Args:
        stats: 수집한 지표.
        now: 기준 시각.

    Returns:
        점검 결과 목록 (항상 같은 순서·개수).
    """
    return [
        _seed_coverage(stats),
        _rss_pass_rate(stats),
        _rss_verification_age(stats, now),
        _collect_freshness(stats, now),
        _retention(stats, now),
        _ranking_coverage(stats),
        _quota(stats),
        _unclassified_rate(stats),
        _channel_limit(stats),
    ]


def _unknown(key: str, title: str, what: str) -> Check:
    """조회하지 못한 지표를 명시적으로 표시한다."""
    return Check(key, title, Level.UNKNOWN, f"조회 불가 — {what}")


def _seed_coverage(stats: OpsStats) -> Check:
    title = "시드 커버리지"
    if stats.seed_counts is None:
        return _unknown("seed_coverage", title, "시드 채널 수를 읽지 못했습니다.")

    empty = [name for name, count in stats.seed_counts.items() if count == 0]
    if empty:
        return Check(
            "seed_coverage",
            title,
            Level.CRITICAL,
            f"시드가 없는 카테고리: {', '.join(empty)} — 이 카테고리의 보드는 계속 빕니다. "
            "`discover_seeds --only <id>` 로 발굴하세요.",
        )

    thin = [name for name, count in stats.seed_counts.items() if count < SEED_MIN_PER_CATEGORY]
    if thin:
        return Check(
            "seed_coverage",
            title,
            Level.WARN,
            f"시드가 {SEED_MIN_PER_CATEGORY}개 미만인 카테고리: {', '.join(thin)} (D4 기준 10~20개)",
        )

    total = sum(stats.seed_counts.values())
    return Check("seed_coverage", title, Level.OK, f"{len(stats.seed_counts)}개 카테고리 · 시드 {total}개")


def _rss_pass_rate(stats: OpsStats) -> Check:
    title = "RSS 통과율"
    if stats.rss_pass_rate is None:
        return _unknown("rss_pass_rate", title, "RSS 검증 기록이 없습니다.")

    if stats.rss_pass_rate < RSS_PASS_WARN_RATE:
        return Check(
            "rss_pass_rate",
            title,
            Level.WARN,
            f"{stats.rss_pass_rate:.1%} — 실패 채널이 많습니다. `verify_seeds --prune` 로 정리하세요.",
        )
    return Check("rss_pass_rate", title, Level.OK, f"{stats.rss_pass_rate:.1%}")


def _rss_verification_age(stats: OpsStats, now: datetime) -> Check:
    title = "RSS 검증 기록"
    if stats.last_rss_verified_at is None:
        return _unknown("rss_verification_age", title, "검증을 실행한 적이 없습니다.")

    days = (now - stats.last_rss_verified_at).days
    if days > RSS_VERIFY_STALE_DAYS:
        return Check(
            "rss_verification_age",
            title,
            Level.WARN,
            f"{days}일 전 — 통과율 수치가 오래됐습니다. `verify_seeds` 를 다시 실행하세요.",
        )
    return Check("rss_verification_age", title, Level.OK, f"{days}일 전 검증")


def _collect_freshness(stats: OpsStats, now: datetime) -> Check:
    title = "수집 신선도"
    if stats.last_collect_at is None:
        return Check(
            "collect_freshness",
            title,
            Level.CRITICAL,
            "수집 기록이 없습니다 — cron이 한 번도 돌지 않았습니다.",
        )

    hours = (now - stats.last_collect_at).total_seconds() / 3600
    if hours > COLLECT_STALE_HOURS:
        return Check(
            "collect_freshness",
            title,
            Level.CRITICAL,
            f"마지막 수집 {hours:.0f}시간 전 — cron이 멈췄을 수 있습니다 (기준 {COLLECT_STALE_HOURS}시간).",
        )
    return Check("collect_freshness", title, Level.OK, f"마지막 수집 {hours:.1f}시간 전")


def _retention(stats: OpsStats, now: datetime) -> Check:
    title = "보관 정책"
    if stats.oldest_snapshot_at is None:
        return _unknown("retention", title, "가장 오래된 스냅샷 시각을 읽지 못했습니다.")

    days = (now - stats.oldest_snapshot_at).days
    if days > RETENTION_DAYS:
        return Check(
            "retention",
            title,
            Level.CRITICAL,
            f"{days}일 지난 데이터가 남아 있습니다 (한도 {RETENTION_DAYS}일) — "
            "약관 위반입니다. purge가 도는지 확인하세요.",
        )
    return Check("retention", title, Level.OK, f"가장 오래된 데이터 {days}일 전 (한도 {RETENTION_DAYS}일)")


def _ranking_coverage(stats: OpsStats) -> Check:
    title = "랭킹 커버리지"
    if stats.ranked_categories is None:
        return _unknown("ranking_coverage", title, "랭킹 테이블을 읽지 못했습니다.")

    if stats.ranked_categories == 0:
        return Check(
            "ranking_coverage",
            title,
            Level.WARN,
            "랭킹이 비어 있습니다 — 콜드스타트 중이면 정상이며, 스냅샷이 2회 이상 쌓이면 채워집니다.",
        )
    return Check("ranking_coverage", title, Level.OK, f"{stats.ranked_categories}개 카테고리에 랭킹 존재")


def _quota(stats: OpsStats) -> Check:
    title = "쿼터 사용량"
    if stats.quota_used_today is None:
        return _unknown("quota", title, "오늘 사용량을 읽지 못했습니다.")

    used, limit = stats.quota_used_today, stats.quota_limit
    ratio = used / limit if limit else 0.0
    summary = f"{used:,} / {limit:,} ({ratio:.0%})"

    if ratio >= 1.0:
        return Check("quota", title, Level.CRITICAL, f"{summary} — 소진. 남은 주기의 수집이 중단됩니다.")
    if ratio >= QUOTA_WARN_RATIO:
        return Check("quota", title, Level.WARN, f"{summary} — 한도에 근접했습니다.")
    return Check("quota", title, Level.OK, summary)


def _unclassified_rate(stats: OpsStats) -> Check:
    title = "미분류율"
    if stats.unclassified_rate is None:
        return _unknown("unclassified_rate", title, "분류 결과를 읽지 못했습니다.")

    rate = stats.unclassified_rate
    if rate > UNCLASSIFIED_WARN_RATE:
        return Check(
            "unclassified_rate",
            title,
            Level.WARN,
            f"{rate:.1%} — 기준 {UNCLASSIFIED_WARN_RATE:.0%} 초과. "
            "2주 지속되면 LLM 분류 도입을 검토합니다 (D10).",
        )
    return Check("unclassified_rate", title, Level.OK, f"{rate:.1%} (기준 {UNCLASSIFIED_WARN_RATE:.0%})")


def _channel_limit(stats: OpsStats) -> Check:
    title = "추적 채널 수"
    if stats.tracked_channels is None:
        return _unknown("channel_limit", title, "추적 채널 수를 읽지 못했습니다.")

    count = stats.tracked_channels
    summary = f"{count:,} / {TRACKED_CHANNEL_LIMIT:,}"

    if count > TRACKED_CHANNEL_LIMIT:
        return Check(
            "channel_limit",
            title,
            Level.CRITICAL,
            f"{summary} — 상한 초과. 졸업이 동작하는지 확인하세요 (D11).",
        )
    if count >= TRACKED_CHANNEL_LIMIT * CHANNEL_LIMIT_WARN_RATIO:
        return Check(
            "channel_limit", title, Level.WARN, f"{summary} — 상한에 근접. 신규 편입이 졸업과 교환됩니다."
        )
    return Check("channel_limit", title, Level.OK, summary)


def worst_level(checks: list[Check]) -> Level:
    """가장 심각한 등급을 돌려준다 (상황판 요약용)."""
    order = [Level.CRITICAL, Level.WARN, Level.UNKNOWN, Level.OK]
    levels = {c.level for c in checks}
    for level in order:
        if level in levels:
            return level
    return Level.OK

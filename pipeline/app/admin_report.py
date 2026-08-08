"""운영 리포트 렌더링 (FR-9, NFR-10).

읽기 전용 산출물이다 — 웹에서 작업을 트리거하지 않는다 (FR-9 확정).
public 리포에 커밋되므로 키·연락처·원문 식별자는 담지 않는다 (NFR-10, D13).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.admin_checks import Check, Level, OpsStats, worst_level

KST = timedelta(hours=9)

LEVEL_MARK = {
    Level.OK: "✅",
    Level.WARN: "⚠️",
    Level.CRITICAL: "🔴",
    Level.UNKNOWN: "❔",
}

SUMMARY_TEXT = {
    Level.OK: "정상",
    Level.WARN: "주의",
    Level.CRITICAL: "조치 필요",
    Level.UNKNOWN: "일부 조회 불가",
}


def render_report(stats: OpsStats, checks: list[Check], *, now: datetime) -> str:
    """상황판 마크다운을 만든다.

    Args:
        stats: 수집한 지표.
        checks: 자동 점검 결과.
        now: 생성 시각.

    Returns:
        마크다운 문서 본문.
    """
    overall = worst_level(checks)
    stamp = (now + KST).strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 운영 상황판 — utube-trend-tracer",
        "",
        f"**{LEVEL_MARK[overall]} {SUMMARY_TEXT[overall]}** · 생성 {stamp} KST",
        "",
        "> 자동 생성 문서입니다. 수집 cron이 돌 때마다 갱신됩니다.",
        "> 읽기 전용 산출물이며, 조치는 아래 런북의 명령으로 실행합니다 (FR-9).",
        "",
        "## 자동 점검",
        "",
        "| | 항목 | 상태 |",
        "|---|------|------|",
    ]

    for check in checks:
        lines.append(f"| {LEVEL_MARK[check.level]} | {check.title} | {check.detail} |")

    lines += [
        "",
        "## 적재 현황",
        "",
        "| 지표 | 값 |",
        "|------|-----|",
        f"| 카테고리 | {_num(stats.categories)} |",
        f"| 시드 채널 | {_seed_total(stats)} |",
        f"| 추적 채널 | {_num(stats.tracked_channels)} |",
        f"| 영상 스냅샷 행 | {_num(stats.video_snapshot_rows)} |",
        f"| 랭킹 보유 카테고리 | {_num(stats.ranked_categories)} |",
        f"| 오늘 쿼터 | {_quota(stats)} |",
        f"| 마지막 수집 | {_time(stats.last_collect_at)} |",
        "",
        "## 카테고리별 시드",
        "",
    ]

    if stats.seed_counts is None:
        lines.append("조회 불가 — 시드 파일을 읽지 못했습니다.")
    else:
        lines += ["| 대분류 | 시드 수 |", "|--------|---------|"]
        lines += [f"| {name} | {count} |" for name, count in sorted(stats.seed_counts.items())]

    lines += [
        "",
        "## 다음 조치",
        "",
    ]

    actionable = [c for c in checks if c.level in (Level.CRITICAL, Level.WARN, Level.UNKNOWN)]
    if actionable:
        lines += [f"- **{c.title}** — {c.detail}" for c in actionable]
    else:
        lines.append("- 조치가 필요한 항목이 없습니다.")

    lines += [
        "",
        "운영 절차는 [RUNBOOK.md](../RUNBOOK.md) 를 따릅니다.",
        "",
    ]

    return "\n".join(lines)


def _num(value: int | None) -> str:
    return f"{value:,}" if value is not None else "조회 불가"


def _seed_total(stats: OpsStats) -> str:
    if stats.seed_counts is None:
        return "조회 불가"
    return f"{sum(stats.seed_counts.values()):,}"


def _quota(stats: OpsStats) -> str:
    if stats.quota_used_today is None:
        return "조회 불가"
    return f"{stats.quota_used_today:,} / {stats.quota_limit:,}"


def _time(value: datetime | None) -> str:
    if value is None:
        return "기록 없음"
    return (value + KST).strftime("%Y-%m-%d %H:%M KST")

"""운영 상황판 생성 (M5, FR-9, NFR-9, NFR-10).

수집 cron 직후에 이어 실행한다. 지표를 하나씩 따로 조회해서, 어느 하나가
실패해도 나머지는 그대로 담는다 — 상황판이 장애와 함께 죽으면 쓸모가 없다.

산출물은 `docs/reports/status.md` 이며 public 리포에 커밋된다 (D13).
키·연락처는 담지 않는다 (NFR-10).

사용:
    python -m scripts.build_report
    python -m scripts.build_report --stdout   # 파일로 쓰지 않고 출력만
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import yaml
from supabase import create_client

from app.admin_checks import Level, OpsStats, run_checks, worst_level
from app.admin_report import render_report
from app.config import PROJECT_ROOT, ConfigError, Settings, ensure_ssl_certificates

REPORT_PATH = PROJECT_ROOT / "docs" / "reports" / "status.md"
SEEDS_PATH = PROJECT_ROOT / "config" / "seeds.yaml"
VERIFY_LOG_PATH = PROJECT_ROOT / "docs" / "reports" / "rss_verify.json"

T = TypeVar("T")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="운영 상황판 생성")
    parser.add_argument("--stdout", action="store_true", help="파일로 쓰지 않고 표준출력으로만")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_ssl_certificates()
    now = datetime.now(UTC)

    stats = OpsStats()
    _fill_from_config(stats)

    try:
        settings = Settings.from_env(load_dotenv_file=True)
        client = create_client(settings.supabase_url, settings.supabase_service_key)
    except (ConfigError, Exception) as exc:  # noqa: BLE001 - 접속 실패도 상황판에 담는다
        print(f"[경고] DB 접속 실패 — 지표를 조회하지 못했습니다: {type(exc).__name__}")
        client = None

    if client is not None:
        _fill_from_db(stats, client, now)

    checks = run_checks(stats, now=now)
    report = render_report(stats, checks, now=now)

    if args.stdout:
        print(report)
    else:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"{REPORT_PATH} 갱신 완료")

    for check in checks:
        if check.level is not Level.OK:
            print(f"  [{check.level.value}] {check.title}: {check.detail}")

    # 상황판 생성 자체는 실패시키지 않는다 — cron이 붉게 물들면 진짜 장애를 놓친다.
    print(f"\n종합: {worst_level(checks).value}")
    return 0


def _fill_from_config(stats: OpsStats) -> None:
    """리포의 설정 파일에서 읽는 지표 (DB 없이도 채워진다)."""
    seeds = _safe(lambda: yaml.safe_load(SEEDS_PATH.read_text(encoding="utf-8")))
    if isinstance(seeds, dict):
        channels = seeds.get("channels") or {}
        stats.seed_counts = {str(k): len(v or []) for k, v in channels.items()}

    verify = _safe(lambda: yaml.safe_load(VERIFY_LOG_PATH.read_text(encoding="utf-8")))
    if isinstance(verify, list) and verify:
        passed = sum(1 for r in verify if r.get("ok"))
        stats.rss_pass_rate = passed / len(verify)
        stats.last_rss_verified_at = _safe(lambda: _mtime(VERIFY_LOG_PATH))


def _fill_from_db(stats: OpsStats, client: Any, now: datetime) -> None:
    """DB 지표를 하나씩 따로 조회한다 — 한 쿼리가 실패해도 나머지는 채운다 (NFR-9)."""
    stats.categories = _safe(lambda: _count(client, "ut_categories"))
    stats.tracked_channels = _safe(lambda: _count(client, "ut_channels", ("tracked", True)))
    stats.video_snapshot_rows = _safe(lambda: _count(client, "ut_video_snapshots"))

    stats.last_collect_at = _safe(
        lambda: _parse_dt(
            _first(client, "ut_collect_runs", "started_at", order="started_at", desc=True)
        )
    )
    stats.oldest_snapshot_at = _safe(
        lambda: _parse_dt(_first(client, "ut_video_snapshots", "captured_at", order="captured_at"))
    )

    stats.quota_used_today = _safe(lambda: _quota_today(client, now))
    stats.ranked_categories = _safe(lambda: _ranked_categories(client))
    stats.unclassified_rate = _safe(lambda: _unclassified_rate(client))


def _count(client: Any, table: str, eq: tuple[str, Any] | None = None) -> int:
    query = client.table(table).select("*", count="exact").limit(1)
    if eq:
        query = query.eq(eq[0], eq[1])
    return int(query.execute().count or 0)


def _first(client: Any, table: str, column: str, *, order: str, desc: bool = False) -> Any:
    rows = (
        client.table(table)
        .select(column)
        .order(order, desc=desc)
        .limit(1)
        .execute()
        .data
    )
    return rows[0][column] if rows else None


def _quota_today(client: Any, now: datetime) -> int:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    rows = client.table("ut_collect_runs").select("quota_used").gte("started_at", day_start).execute().data
    return sum(int(r.get("quota_used") or 0) for r in rows)


def _ranked_categories(client: Any) -> int:
    rows = client.table("ut_trend_scores").select("category_id").execute().data
    return len({str(r["category_id"]) for r in rows})


def _unclassified_rate(client: Any) -> float:
    total = _count(client, "ut_videos")
    if total == 0:
        return 0.0
    unclassified = _count(client, "ut_videos", ("unclassified", True))
    return unclassified / total


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def _safe(action: Callable[[], T]) -> T | None:
    """조회 실패를 None으로 바꾼다 — 그 항목만 '조회 불가'가 된다 (NFR-9)."""
    try:
        return action()
    except Exception:  # noqa: BLE001 - 어떤 실패든 상황판을 멈추지 않는다
        return None


if __name__ == "__main__":
    sys.exit(main())

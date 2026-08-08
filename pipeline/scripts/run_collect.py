"""수집 주기 실행 (M2, FR-6).

cron이 하루 3회 호출한다. 오늘 이미 쓴 쿼터를 DB에서 읽어 이어 쓰므로,
같은 날 여러 번 돌아도 일 한도를 넘지 않는다 (NFR-4).

사용:
    python -m scripts.run_collect
    python -m scripts.run_collect --limit 20   # 채널 수를 줄여 시험 실행
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from supabase import create_client

from app.blocklist import load_blocklist
from app.categories import load_categories
from app.classifier import KeywordClassifier
from app.collect import collect_once
from app.config import ConfigError, Settings, ensure_ssl_certificates
from app.quota import DAILY_QUOTA_LIMIT, QuotaBudget
from app.store import Store
from app.youtube import YouTubeClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="수집 한 주기 실행")
    parser.add_argument("--limit", type=int, help="추적 채널 수 상한 (시험 실행용)")
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

    # 오늘 이미 쓴 쿼터에서 이어 쓴다 (cron 하루 3회, NFR-4).
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    used_today = store.quota_used_since(day_start)
    budget = QuotaBudget(daily_limit=DAILY_QUOTA_LIMIT, used=used_today)
    print(f"오늘 사용 쿼터 {used_today:,} / {DAILY_QUOTA_LIMIT:,} (남음 {budget.remaining:,})")

    if budget.exhausted:
        print("쿼터 소진 — 이번 주기 수집을 건너뜁니다 (서빙은 영향 없음).")
        return 0

    if args.limit:
        original = store.tracked_channels

        def limited() -> list[dict]:  # type: ignore[type-arg]
            return original()[: args.limit]

        store.tracked_channels = limited  # type: ignore[method-assign]

    report = collect_once(
        store=store,
        youtube=YouTubeClient(api_key=settings.youtube_api_key),
        classifier=KeywordClassifier(load_categories()),
        blocklist=load_blocklist(),
        budget=budget,
        now=now,
    )

    print(
        f"\n수집 완료 ({report.started_at.isoformat()})\n"
        f"  채널 스냅샷 {report.channels_updated}개\n"
        f"  영상 스냅샷 {report.videos_updated}개 (RSS 신규 {report.new_videos}개)\n"
        f"  삭제·비공개 제거 {report.deleted_videos}개\n"
        f"  졸업 채널 {report.graduated_channels}개\n"
        f"  미분류율 {report.unclassified_rate:.1%}\n"
        f"  쿼터 사용 {report.quota_used:,}유닛"
    )
    if report.errors:
        print(f"\n경고 {len(report.errors)}건:")
        for error in report.errors:
            print(f"  - {error}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

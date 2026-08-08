"""시드 채널을 DB에 등재한다 (M2, D4).

`config/seeds.yaml`의 채널을 `ut_channels`에 넣는다. 시드는 `is_seed=true`로
표시해 자동 졸업 대상에서 제외한다 (D11).

사용:
    python -m scripts.sync_seeds
    python -m scripts.sync_seeds --dry-run
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import yaml
from supabase import create_client

from app.config import PROJECT_ROOT, ConfigError, Settings, ensure_ssl_certificates
from app.store import Store

SEEDS_PATH = PROJECT_ROOT / "config" / "seeds.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="시드 채널을 ut_channels에 등재")
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 요약만 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_ssl_certificates()

    if not SEEDS_PATH.exists():
        print(f"시드 파일이 없습니다: {SEEDS_PATH}")
        return 1

    data = yaml.safe_load(SEEDS_PATH.read_text(encoding="utf-8")) or {}
    rows: list[dict[str, Any]] = []
    for parent, channels in (data.get("channels") or {}).items():
        for channel in channels:
            rows.append(
                {
                    "channel_id": str(channel["id"]),
                    "title": str(channel.get("title", "")),
                    # 국내/해외 태그는 영상 소재 분포로 정하므로 (D9) 여기서는 대분류만 남긴다.
                    "category_ids": [parent],
                    "is_seed": True,
                    "tracked": True,
                }
            )
        print(f"  {parent:10} {len(channels):>3}개")

    print(f"\n총 {len(rows)}개 채널")
    if args.dry_run:
        print("dry-run — DB에 쓰지 않고 종료합니다.")
        return 0

    try:
        settings = Settings.from_env(load_dotenv_file=True)
    except ConfigError as exc:
        print(f"설정 오류: {exc}")
        return 1

    store = Store(create_client(settings.supabase_url, settings.supabase_service_key))
    count = store.upsert_channels(rows)
    print(f"ut_channels 등재 완료 — {count}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())

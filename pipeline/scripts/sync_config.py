"""config → DB 동기화 (M1, FR-1).

`config/categories.yaml`을 `ut_categories`에 반영한다. YAML이 단일 진실이며
DB는 그 사본이다 — YAML에서 빠진 카테고리는 삭제하지 않고 비활성화만 한다.

사용:
    python -m scripts.sync_config            # 동기화 실행
    python -m scripts.sync_config --dry-run  # 반영할 내용만 출력
"""

from __future__ import annotations

import argparse
import sys

from supabase import create_client

from app.categories import CategoryConfigError, load_categories
from app.category_sync import sync_categories
from app.config import ConfigError, Settings, ensure_ssl_certificates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="카테고리 정의를 DB에 동기화")
    parser.add_argument("--dry-run", action="store_true", help="DB에 쓰지 않고 내용만 출력")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_ssl_certificates()

    try:
        categories = load_categories()
    except CategoryConfigError as exc:
        print(f"카테고리 정의 오류: {exc}")
        return 1

    print(f"카테고리 {len(categories)}개 (대분류 {len({c.parent for c in categories})}개)")
    for category in categories:
        print(
            f"  {category.id:22} {category.name:16} "
            f"키워드 {len(category.keywords):>3}개 · w={category.weight}"
        )

    if args.dry_run:
        print("\ndry-run — DB에 쓰지 않고 종료합니다.")
        return 0

    try:
        settings = Settings.from_env(load_dotenv_file=True)
    except ConfigError as exc:
        print(f"설정 오류: {exc}")
        return 1

    client = create_client(settings.supabase_url, settings.supabase_service_key)
    result = sync_categories(client, categories)

    print(f"\n동기화 완료 — upsert {result.upserted}건, 비활성화 {result.disabled}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""시드 채널 발굴 (M1, D4).

카테고리별 검색어로 채널을 찾아 통계를 붙이고, 분류기로 카테고리를 확인해
`config/seeds.yaml` 초안을 만든다. `search.list`는 100유닛/회로 비싸므로
검색어 수 × 100유닛을 미리 계산해 보여주고, 예산을 넘으면 실행하지 않는다 (D14).

사용:
    python -m scripts.discover_seeds --dry-run          # 쿼터 계산만
    python -m scripts.discover_seeds                     # 전체 카테고리 발굴
    python -m scripts.discover_seeds --only food,travel  # 일부만
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import yaml

from app.categories import load_categories
from app.classifier import KeywordClassifier
from app.config import PROJECT_ROOT, ConfigError, Settings, ensure_ssl_certificates
from app.youtube import COST_SEARCH, YouTubeApiError, YouTubeClient

SEEDS_PATH = PROJECT_ROOT / "config" / "seeds.yaml"

# 대분류별 검색어 — 한국어 검색어로 한국 채널을 노린다 (D9).
SEARCH_QUERIES: dict[str, list[str]] = {
    "food": ["먹방", "맛집 리뷰", "요리 레시피"],
    "travel": ["여행 브이로그", "국내여행", "해외여행"],
    "tech": ["IT 리뷰", "스마트폰 리뷰", "노트북 추천"],
    "aicoding": ["바이브코딩", "AI 활용", "개발자 코딩"],
    "vlog": ["일상 브이로그", "자취 브이로그"],
    "fitness": ["홈트레이닝", "헬스 운동", "다이어트"],
}

# 시드 품질 기준 — 너무 작은 채널은 시계열이 의미 없고, 휴면 채널은 수집 낭비다.
MIN_SUBSCRIBERS = 1_000
MAX_PER_PARENT = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="카테고리별 시드 채널 발굴")
    parser.add_argument("--only", help="쉼표로 구분한 대분류 id (예: food,travel)")
    parser.add_argument("--dry-run", action="store_true", help="쿼터 예상 사용량만 계산")
    parser.add_argument(
        "--budget", type=int, default=6_000, help="이번 실행에 허용할 쿼터 유닛 (기본 6000, D14)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_ssl_certificates()

    parents = list(SEARCH_QUERIES)
    if args.only:
        requested = [p.strip() for p in args.only.split(",") if p.strip()]
        unknown = [p for p in requested if p not in SEARCH_QUERIES]
        if unknown:
            print(f"알 수 없는 대분류: {unknown}. 가능한 값: {parents}")
            return 1
        parents = requested

    query_count = sum(len(SEARCH_QUERIES[p]) for p in parents)
    estimated = query_count * COST_SEARCH
    print(f"대상 대분류 {len(parents)}개 · 검색어 {query_count}개 · 예상 쿼터 {estimated:,}유닛")

    if estimated > args.budget:
        print(f"예산({args.budget:,}유닛)을 초과합니다. --only 로 범위를 줄이세요.")
        return 1
    if args.dry_run:
        print("dry-run — 호출하지 않고 종료합니다.")
        return 0

    try:
        settings = Settings.from_env(load_dotenv_file=True)
    except ConfigError as exc:
        print(f"설정 오류: {exc}")
        return 1

    client = YouTubeClient(api_key=settings.youtube_api_key)
    classifier = KeywordClassifier(load_categories())

    seeds: dict[str, list[dict[str, Any]]] = {}
    for parent in parents:
        found = _discover_parent(client, classifier, parent)
        seeds[parent] = found
        print(f"  {parent}: {len(found)}개 채널 (누적 쿼터 {client.quota_used:,}유닛)")

    _write_seeds(seeds, parents)
    print(f"\n{SEEDS_PATH} 갱신 완료 · 총 쿼터 {client.quota_used:,}유닛 사용")
    return 0


def _discover_parent(
    client: YouTubeClient, classifier: KeywordClassifier, parent: str
) -> list[dict[str, Any]]:
    """대분류 하나의 시드 후보를 찾는다."""
    candidate_ids: dict[str, str] = {}
    for query in SEARCH_QUERIES[parent]:
        try:
            for hit in client.search_channels(query, max_results=25):
                candidate_ids.setdefault(hit["channel_id"], query)
        except YouTubeApiError as exc:
            print(f"  [경고] '{query}' 검색 실패 — {exc}")

    if not candidate_ids:
        return []

    try:
        details = client.fetch_channels(list(candidate_ids))
    except YouTubeApiError as exc:
        print(f"  [경고] {parent} 채널 통계 조회 실패 — {exc}")
        return []

    accepted: list[dict[str, Any]] = []
    for channel in details:
        if channel["subscriber_count"] < MIN_SUBSCRIBERS:
            continue
        result = classifier.classify(channel["title"], description=channel["description"])
        if result.parent != parent:
            # 검색 결과가 다른 소재로 분류되면 그 카테고리의 시드로 두지 않는다.
            continue
        # 국내/해외 태그는 채널이 아니라 영상 소재 단위로 판정한다 (D9) —
        # 채널 설명만 보면 오탐이 잦다. 채널 카테고리는 M2에서 영상 분포로 정한다.
        accepted.append(
            {
                "id": channel["channel_id"],
                "title": channel["title"],
                "subscribers": channel["subscriber_count"],
                "discovered_by": candidate_ids[channel["channel_id"]],
            }
        )

    accepted.sort(key=lambda c: c["subscribers"], reverse=True)
    return accepted[:MAX_PER_PARENT]


def _write_seeds(seeds: dict[str, list[dict[str, Any]]], parents: list[str]) -> None:
    """seeds.yaml을 갱신한다 — 지정하지 않은 대분류의 기존 시드는 보존한다."""
    existing: dict[str, Any] = {"version": 1, "channels": {}}
    if SEEDS_PATH.exists():
        loaded = yaml.safe_load(SEEDS_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            existing = loaded
            existing.setdefault("channels", {})

    for parent in parents:
        existing["channels"][parent] = seeds.get(parent, [])

    header = (
        "# 시드 채널 (SPEC FR-6, D4)\n"
        "#\n"
        "# scripts/discover_seeds.py 가 생성한다. 손으로 추가·삭제해도 된다 —\n"
        "# 재실행 시 지정한 대분류만 덮어쓰고 나머지는 보존한다.\n"
        "# 국내/해외 태그는 여기 없다 — 영상 소재 단위로 판정하며 (D9),\n"
        "# 채널 카테고리는 M2에서 그 채널 영상들의 분포로 정한다.\n\n"
    )
    SEEDS_PATH.write_text(
        header + yaml.safe_dump(existing, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())

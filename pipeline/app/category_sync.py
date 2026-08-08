"""config/categories.yaml → `ut_categories` 동기화 (FR-1).

YAML이 단일 진실이고 DB는 그 사본이다. YAML에서 빠진 카테고리는
삭제하지 않고 비활성화만 한다 — 참조하는 랭킹 이력을 잃지 않기 위해서다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.categories import CategoryDefinition

CATEGORIES_TABLE = "ut_categories"


class SupabaseLike(Protocol):
    """테스트에서 가짜로 대체할 수 있도록 필요한 부분만 선언한다."""

    def table(self, name: str) -> Any: ...


@dataclass(frozen=True)
class SyncResult:
    """동기화 결과 요약.

    Attributes:
        upserted: 갱신·삽입된 카테고리 수.
        disabled: YAML에서 빠져 비활성화된 카테고리 수.
    """

    upserted: int
    disabled: int


def sync_categories(client: SupabaseLike, definitions: Sequence[CategoryDefinition]) -> SyncResult:
    """카테고리 정의를 DB에 반영한다.

    Args:
        client: Supabase 클라이언트 (service key 사용).
        definitions: `load_categories()` 결과.

    Returns:
        upsert·비활성화 건수를 담은 SyncResult.
    """
    if not definitions:
        # 설정 실수로 전체 카테고리가 꺼지는 사고를 막는다.
        return SyncResult(upserted=0, disabled=0)

    rows = [d.to_row() for d in definitions]
    table = client.table(CATEGORIES_TABLE)
    table.upsert(rows, on_conflict="id").execute()

    active_ids = [d.id for d in definitions]
    existing = client.table(CATEGORIES_TABLE).select("id").execute()
    existing_ids = [str(r["id"]) for r in (getattr(existing, "data", None) or [])]
    stale_ids = [i for i in existing_ids if i not in active_ids]

    if stale_ids:
        # 비활성화 대상을 직접 지정한다 — 부정 필터(not_.in_)를 쓰면
        # 인자를 뒤집었을 때 활성 카테고리를 통째로 꺼버린다.
        client.table(CATEGORIES_TABLE).update({"enabled": False}).in_("id", stale_ids).execute()

    return SyncResult(upserted=len(rows), disabled=len(stale_ids))

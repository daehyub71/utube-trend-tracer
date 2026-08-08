"""config → ut_categories 동기화 테스트 (FR-1).

YAML이 단일 진실이며 DB는 그 사본이다. 네트워크 없이 검증하기 위해
Supabase 클라이언트는 가짜 객체로 대체한다.
"""

from typing import Any

from app.categories import CategoryDefinition
from app.category_sync import sync_categories


class FakeTable:
    """upsert / update 호출을 기록하는 가짜 테이블."""

    def __init__(self, existing_ids: list[str]) -> None:
        self.existing_ids = existing_ids
        self.upserted: list[dict[str, Any]] = []
        self.disabled_ids: list[str] = []
        self._pending_disable = False

    def select(self, _columns: str) -> "FakeTable":
        return self

    def upsert(self, rows: list[dict[str, Any]], **_kwargs: Any) -> "FakeTable":
        self.upserted = rows
        return self

    def update(self, values: dict[str, Any]) -> "FakeTable":
        self._pending_disable = values.get("enabled") is False
        return self

    def in_(self, _column: str, values: list[str]) -> "FakeTable":
        # 실제 PostgREST와 동일하게 "여기 있는 id를 대상으로" 해석한다.
        if self._pending_disable:
            self.disabled_ids = list(values)
        return self

    def execute(self) -> Any:
        return type("Result", (), {"data": [{"id": i} for i in self.existing_ids]})()


class FakeClient:
    def __init__(self, existing_ids: list[str] | None = None) -> None:
        self.table_obj = FakeTable(existing_ids or [])
        self.requested_tables: list[str] = []

    def table(self, name: str) -> FakeTable:
        self.requested_tables.append(name)
        return self.table_obj


def definitions() -> list[CategoryDefinition]:
    return [
        CategoryDefinition(
            id="food_domestic", name="음식 > 국내", parent="food", tag="domestic",
            keywords=("먹방",), weight=1.0,
        ),
        CategoryDefinition(
            id="food_overseas", name="음식 > 해외", parent="food", tag="overseas",
            keywords=("먹방",), weight=1.0,
        ),
    ]


def test_sync_writes_to_ut_categories_table() -> None:
    """ut_ 접두어 테이블에 쓴다 (SPEC §6)."""
    client = FakeClient()

    sync_categories(client, definitions())

    assert "ut_categories" in client.requested_tables


def test_sync_upserts_all_definitions() -> None:
    """모든 카테고리를 upsert한다 — 재실행해도 중복되지 않아야 한다."""
    client = FakeClient()

    result = sync_categories(client, definitions())

    assert len(client.table_obj.upserted) == 2
    assert {r["id"] for r in client.table_obj.upserted} == {"food_domestic", "food_overseas"}
    assert result.upserted == 2


def test_sync_row_shape_matches_schema() -> None:
    """전송 행이 ut_categories 컬럼과 일치한다."""
    client = FakeClient()

    sync_categories(client, definitions())

    row = client.table_obj.upserted[0]
    assert set(row) == {"id", "name", "parent", "tag", "keywords", "weight", "enabled"}
    assert row["keywords"] == ["먹방"]


def test_sync_disables_categories_removed_from_yaml() -> None:
    """YAML에서 빠진 카테고리는 삭제 대신 비활성화한다.

    삭제하면 그 카테고리를 참조하는 ut_trend_scores 행이 함께 사라진다 —
    과거 랭킹 이력을 잃지 않도록 enabled=false 로만 내린다.
    """
    client = FakeClient(existing_ids=["food_domestic", "food_overseas", "legacy_category"])

    result = sync_categories(client, definitions())

    assert client.table_obj.disabled_ids == ["legacy_category"]
    assert result.disabled == 1


def test_sync_with_no_stale_categories_disables_nothing() -> None:
    client = FakeClient(existing_ids=["food_domestic", "food_overseas"])

    result = sync_categories(client, definitions())

    assert result.disabled == 0


def test_sync_empty_definitions_is_noop() -> None:
    """정의가 비면 아무것도 지우지 않는다 — 설정 실수로 전체가 꺼지는 사고 방지."""
    client = FakeClient(existing_ids=["food_domestic"])

    result = sync_categories(client, [])

    assert result.upserted == 0
    assert result.disabled == 0
    assert client.table_obj.disabled_ids == []

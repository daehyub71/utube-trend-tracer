"""카테고리 정의 로딩·검증 테스트 (FR-1, D3, D9).

확장형 체계의 핵심 — 코드 수정 없이 YAML만 고쳐 카테고리를 추가할 수 있어야 한다.
"""

from pathlib import Path

import pytest
import yaml

from app.categories import CategoryConfigError, CategoryDefinition, load_categories

VALID_YAML = """
version: 1
tags:
  domestic:
    name: 국내
  overseas:
    name: 해외
    keywords: [해외, 일본]
parents:
  - id: food
    name: 음식
    weight: 1.0
    keywords: [먹방, 맛집]
  - id: aicoding
    name: 바이브코딩·AI
    weight: 1.1
    keywords: [AI, 코딩]
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "categories.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_expands_parents_by_tags(tmp_path: Path) -> None:
    """대분류 N개 × 태그 2개 = 카테고리 2N개로 전개된다."""
    categories = load_categories(write(tmp_path, VALID_YAML))

    assert len(categories) == 4
    assert {c.id for c in categories} == {
        "food_domestic",
        "food_overseas",
        "aicoding_domestic",
        "aicoding_overseas",
    }


def test_load_composes_name_and_fields(tmp_path: Path) -> None:
    """전개된 카테고리는 대분류의 이름·가중치·키워드를 물려받는다."""
    by_id = {c.id: c for c in load_categories(write(tmp_path, VALID_YAML))}

    food_overseas = by_id["food_overseas"]
    assert food_overseas.name == "음식 > 해외"
    assert food_overseas.parent == "food"
    assert food_overseas.tag == "overseas"
    assert food_overseas.weight == 1.0
    assert food_overseas.keywords == ("먹방", "맛집")  # 불변 tuple로 보관

    assert by_id["aicoding_domestic"].weight == 1.1


def test_load_real_config_file() -> None:
    """리포에 커밋된 실제 config/categories.yaml이 유효해야 한다 (D3: 6개 대분류)."""
    categories = load_categories()

    parents = {c.parent for c in categories}
    assert parents == {"food", "travel", "tech", "aicoding", "vlog", "fitness"}
    assert len(categories) == 12  # 6 대분류 × 2 태그
    assert all(c.keywords for c in categories)


def test_load_rejects_duplicate_parent_id(tmp_path: Path) -> None:
    """대분류 id가 중복되면 즉시 실패한다 (조용한 덮어쓰기 금지)."""
    text = VALID_YAML + """
  - id: food
    name: 음식 복제
    weight: 1.0
    keywords: [중복]
"""
    with pytest.raises(CategoryConfigError, match="중복"):
        load_categories(write(tmp_path, text))


def test_load_rejects_empty_keywords(tmp_path: Path) -> None:
    """키워드가 없는 대분류는 아무것도 분류하지 못하므로 실패시킨다."""
    data = yaml.safe_load(VALID_YAML)
    data["parents"][0]["keywords"] = []
    text = yaml.safe_dump(data, allow_unicode=True)

    with pytest.raises(CategoryConfigError, match="keywords"):
        load_categories(write(tmp_path, text))


def test_load_rejects_missing_parents_section(tmp_path: Path) -> None:
    """parents 섹션이 없으면 실패한다."""
    with pytest.raises(CategoryConfigError, match="parents"):
        load_categories(write(tmp_path, "version: 1\ntags: {domestic: {name: 국내}}\n"))


def test_definition_to_db_row_matches_schema(tmp_path: Path) -> None:
    """DB 동기화용 dict가 ut_categories 컬럼과 맞아야 한다."""
    category = load_categories(write(tmp_path, VALID_YAML))[0]

    row = category.to_row()

    assert set(row) == {"id", "name", "parent", "tag", "keywords", "weight", "enabled"}
    assert row["enabled"] is True


def test_definition_is_immutable(tmp_path: Path) -> None:
    """정의는 로드 후 변경되지 않아야 한다 (분류 중 오염 방지)."""
    category = load_categories(write(tmp_path, VALID_YAML))[0]

    with pytest.raises(AttributeError):
        category.weight = 2.0  # type: ignore[misc]

    assert isinstance(category, CategoryDefinition)

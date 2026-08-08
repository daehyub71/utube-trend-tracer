"""카테고리 정의 로딩·검증 (FR-1, D3, D9).

`config/categories.yaml`의 대분류 × 태그를 카테고리로 전개한다.
코드 수정 없이 YAML만 고쳐 카테고리를 추가할 수 있어야 하므로,
잘못된 정의는 조용히 넘기지 않고 CategoryConfigError로 즉시 실패시킨다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import PROJECT_ROOT

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "categories.yaml"


class CategoryConfigError(RuntimeError):
    """카테고리 정의가 없거나 형식이 잘못된 경우."""


@dataclass(frozen=True)
class CategoryDefinition:
    """전개된 카테고리 하나 (대분류 × 태그).

    Attributes:
        id: `{parent}_{tag}` 형식의 식별자. 예: `food_overseas`.
        name: 표시용 이름. 예: `음식 > 해외`.
        parent: 대분류 id.
        tag: `domestic` 또는 `overseas` — 소재 구분 (D9).
        keywords: 대분류 매칭 키워드.
        weight: 소재가 겹칠 때의 우선순위 가중치.
    """

    id: str
    name: str
    parent: str
    tag: str
    keywords: tuple[str, ...] = field(default=())
    weight: float = 1.0

    def to_row(self) -> dict[str, Any]:
        """`ut_categories` 테이블에 넣을 dict를 만든다."""
        return {
            "id": self.id,
            "name": self.name,
            "parent": self.parent,
            "tag": self.tag,
            "keywords": list(self.keywords),
            "weight": self.weight,
            "enabled": True,
        }


@dataclass(frozen=True)
class TagDefinition:
    """국내/해외 태그 정의.

    Attributes:
        id: `domestic` 또는 `overseas`.
        name: 표시용 이름.
        keywords: 이 태그로 판정하는 키워드. 기본 태그(domestic)는 비어 있다.
    """

    id: str
    name: str
    keywords: tuple[str, ...] = field(default=())


def load_tags(path: Path | None = None) -> dict[str, TagDefinition]:
    """태그 정의를 읽는다.

    Args:
        path: categories.yaml 경로. 생략하면 `config/categories.yaml`.

    Returns:
        태그 id를 키로 하는 정의 매핑.

    Raises:
        CategoryConfigError: 태그 섹션이 없거나 형식이 잘못된 경우.
    """
    data = _read_yaml(path or DEFAULT_CONFIG_PATH)
    raw_tags = data.get("tags")
    if not isinstance(raw_tags, dict) or not raw_tags:
        raise CategoryConfigError("tags 섹션이 비어 있습니다.")

    tags: dict[str, TagDefinition] = {}
    for tag_id, body in raw_tags.items():
        if not isinstance(body, dict) or not body.get("name"):
            raise CategoryConfigError(f"태그 '{tag_id}' 에 name이 없습니다.")
        keywords = body.get("keywords") or []
        if not isinstance(keywords, list):
            raise CategoryConfigError(f"태그 '{tag_id}' 의 keywords는 목록이어야 합니다.")
        tags[str(tag_id)] = TagDefinition(
            id=str(tag_id), name=str(body["name"]), keywords=tuple(str(k) for k in keywords)
        )
    return tags


def load_categories(path: Path | None = None) -> list[CategoryDefinition]:
    """대분류 × 태그를 카테고리로 전개해 읽는다.

    Args:
        path: categories.yaml 경로. 생략하면 `config/categories.yaml`.

    Returns:
        전개된 카테고리 목록 (대분류 선언 순서 × 태그 선언 순서).

    Raises:
        CategoryConfigError: 정의가 없거나 중복·누락이 있는 경우.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    data = _read_yaml(config_path)

    raw_parents = data.get("parents")
    if not isinstance(raw_parents, list) or not raw_parents:
        raise CategoryConfigError(f"{config_path}: parents 섹션이 비어 있습니다.")

    tags = load_tags(config_path)

    categories: list[CategoryDefinition] = []
    seen: set[str] = set()
    for raw in raw_parents:
        if not isinstance(raw, dict):
            raise CategoryConfigError("parents 항목은 매핑이어야 합니다.")

        parent_id = str(raw.get("id") or "").strip()
        if not parent_id:
            raise CategoryConfigError("대분류에 id가 없습니다.")
        if parent_id in seen:
            raise CategoryConfigError(f"대분류 id '{parent_id}' 가 중복되었습니다.")
        seen.add(parent_id)

        name = str(raw.get("name") or "").strip()
        if not name:
            raise CategoryConfigError(f"대분류 '{parent_id}' 에 name이 없습니다.")

        keywords = raw.get("keywords") or []
        if not isinstance(keywords, list) or not keywords:
            raise CategoryConfigError(f"대분류 '{parent_id}' 의 keywords가 비어 있습니다.")

        try:
            weight = float(raw.get("weight", 1.0))
        except (TypeError, ValueError) as exc:
            raise CategoryConfigError(f"대분류 '{parent_id}' 의 weight가 숫자가 아닙니다.") from exc

        for tag in tags.values():
            categories.append(
                CategoryDefinition(
                    id=f"{parent_id}_{tag.id}",
                    name=f"{name} > {tag.name}",
                    parent=parent_id,
                    tag=tag.id,
                    keywords=tuple(str(k) for k in keywords),
                    weight=weight,
                )
            )

    return categories


def _read_yaml(path: Path) -> dict[str, Any]:
    """YAML 파일을 매핑으로 읽는다."""
    if not path.exists():
        raise CategoryConfigError(f"카테고리 정의 파일이 없습니다: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CategoryConfigError(f"{path}: YAML 파싱 실패 — {exc}") from exc
    if not isinstance(data, dict):
        raise CategoryConfigError(f"{path}: 최상위가 매핑이 아닙니다.")
    return data

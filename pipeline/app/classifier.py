"""키워드 규칙 기반 카테고리 분류 (FR-1, D9, D10).

제목·태그·설명에서 대분류 키워드를 찾아 점수를 매기고, 최고점 대분류를 고른다.
해외 키워드가 잡히면 소재를 해외로 본다 (채널 국적과 무관, D9).
근거가 없으면 미분류 — 미분류는 랭킹에서 제외된다 (D10).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.categories import CategoryDefinition, TagDefinition, load_tags

DEFAULT_TAG = "domestic"


@dataclass(frozen=True)
class Classification:
    """분류 결과.

    Attributes:
        category_id: `{parent}_{tag}` 카테고리 id. 미분류면 None.
        parent: 선택된 대분류 id. 미분류면 None.
        tag: 소재 태그 (`domestic`/`overseas`). 미분류면 None.
        score: 선택된 대분류의 점수 (매칭 수 × 가중치).
        matched_keywords: 대분류 판정에 쓰인 키워드.
        matched_tag_keywords: 해외 판정에 쓰인 키워드.
    """

    category_id: str | None = None
    parent: str | None = None
    tag: str | None = None
    score: float = 0.0
    matched_keywords: tuple[str, ...] = field(default=())
    matched_tag_keywords: tuple[str, ...] = field(default=())

    @property
    def unclassified(self) -> bool:
        """어떤 대분류에도 걸리지 않았는지 여부 (D10)."""
        return self.category_id is None


class KeywordClassifier:
    """카테고리 정의로 텍스트를 분류한다."""

    def __init__(
        self,
        categories: Sequence[CategoryDefinition],
        tags: dict[str, TagDefinition] | None = None,
    ) -> None:
        """분류기를 만든다.

        Args:
            categories: 전개된 카테고리 목록 (`load_categories()` 결과).
            tags: 태그 정의. 생략하면 기본 config에서 읽는다.
        """
        self._tags = tags if tags is not None else load_tags()
        # 대분류별 키워드·가중치 — 전개된 카테고리는 태그만 다르므로 대분류 단위로 접는다.
        self._parents: dict[str, tuple[tuple[str, ...], float]] = {}
        self._parent_order: list[str] = []
        for category in categories:
            if category.parent not in self._parents:
                self._parents[category.parent] = (category.keywords, category.weight)
                self._parent_order.append(category.parent)

    def classify(
        self,
        title: str,
        *,
        tags: Iterable[str] | None = None,
        description: str = "",
    ) -> Classification:
        """제목·태그·설명으로 카테고리를 정한다.

        Args:
            title: 영상/채널 제목.
            tags: 영상 태그 목록.
            description: 설명문.

        Returns:
            분류 결과. 근거가 없으면 `unclassified=True`인 결과.
        """
        haystack = self._normalize(title, tags, description)
        if not haystack:
            return Classification()

        best_parent: str | None = None
        best_score = 0.0
        best_matches: tuple[str, ...] = ()

        for parent in self._parent_order:
            keywords, weight = self._parents[parent]
            matches = tuple(k for k in keywords if k.lower() in haystack)
            if not matches:
                continue
            score = len(matches) * weight
            if score > best_score:
                best_parent, best_score, best_matches = parent, score, matches

        if best_parent is None:
            return Classification()

        tag_id, tag_matches = self._resolve_tag(haystack)
        return Classification(
            category_id=f"{best_parent}_{tag_id}",
            parent=best_parent,
            tag=tag_id,
            score=best_score,
            matched_keywords=best_matches,
            matched_tag_keywords=tag_matches,
        )

    def _resolve_tag(self, haystack: str) -> tuple[str, tuple[str, ...]]:
        """소재 태그를 정한다 — 키워드가 있는 태그가 우선, 없으면 기본값."""
        for tag in self._tags.values():
            if not tag.keywords:
                continue
            matches = tuple(k for k in tag.keywords if k.lower() in haystack)
            if matches:
                return tag.id, matches
        return DEFAULT_TAG, ()

    @staticmethod
    def _normalize(title: str, tags: Iterable[str] | None, description: str) -> str:
        """분류 대상 텍스트를 하나로 합쳐 소문자화한다."""
        parts = [title, " ".join(tags or ()), description]
        return " ".join(p for p in parts if p).lower()

    @staticmethod
    def unclassified_rate(results: Sequence[Classification]) -> float:
        """미분류 비율을 계산한다 — LLM 분류 도입 트리거 지표 (D10).

        Args:
            results: 분류 결과 목록.

        Returns:
            0.0~1.0 사이 비율. 결과가 없으면 0.0.
        """
        if not results:
            return 0.0
        return sum(1 for r in results if r.unclassified) / len(results)

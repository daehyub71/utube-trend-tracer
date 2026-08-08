"""키워드 분류기 테스트 (FR-1, D9, D10).

분류 결과는 랭킹 대상 여부를 가른다 — 미분류는 랭킹에서 제외되므로 (D10),
"애매하면 붙인다"가 아니라 "근거 없으면 미분류"가 규약이다.
"""

import pytest

from app.categories import load_categories
from app.classifier import Classification, KeywordClassifier


@pytest.fixture
def classifier() -> KeywordClassifier:
    """리포에 커밋된 실제 카테고리 정의로 분류기를 만든다."""
    return KeywordClassifier(load_categories())


def test_classify_matches_parent_by_keyword(classifier: KeywordClassifier) -> None:
    """제목의 키워드로 대분류를 정한다."""
    result = classifier.classify("편의점 신상 5종 먹방 리뷰")

    assert result.parent == "food"
    assert result.unclassified is False


def test_classify_defaults_to_domestic(classifier: KeywordClassifier) -> None:
    """해외 키워드가 없으면 국내로 본다 (D9: 태그는 소재 구분)."""
    result = classifier.classify("시장 국밥 3000원의 기적")

    assert result.category_id == "food_domestic"
    assert result.tag == "domestic"


def test_classify_detects_overseas_subject(classifier: KeywordClassifier) -> None:
    """해외 키워드가 잡히면 해외 소재로 본다 — 채널 국적과 무관하다 (D9)."""
    result = classifier.classify("도쿄 라멘 투어 3일차")

    assert result.tag == "overseas"
    assert result.category_id.endswith("_overseas")


def test_classify_unclassified_when_no_keyword(classifier: KeywordClassifier) -> None:
    """어떤 키워드도 안 걸리면 미분류 — 랭킹에서 제외된다 (D10)."""
    result = classifier.classify("오늘의 이야기")

    assert result.unclassified is True
    assert result.category_id is None
    assert result.parent is None


def test_classify_weight_breaks_tie(classifier: KeywordClassifier) -> None:
    """근거가 같으면 가중치가 높은 대분류가 이긴다 (aicoding 1.1 > tech 1.0).

    'AI 스펙' 은 양쪽에 키워드가 1개씩 걸리는 동점 상황이다.
    """
    result = classifier.classify("AI 스펙 정리")

    assert result.parent == "aicoding"


def test_classify_gadget_subject_stays_tech(classifier: KeywordClassifier) -> None:
    """근거가 더 많은 쪽이 이긴다 — 'AI 노트북 언박싱'은 AI가 아니라 기기 리뷰다."""
    result = classifier.classify("AI 노트북 언박싱")

    assert result.parent == "tech"


def test_classify_vlog_yields_to_specific_subject(classifier: KeywordClassifier) -> None:
    """브이로그는 가중치가 낮아 구체적 소재에 양보한다 (vlog 0.9 < travel 1.0)."""
    result = classifier.classify("제주도 여행 브이로그")

    assert result.parent == "travel"


def test_classify_vlog_wins_when_alone(classifier: KeywordClassifier) -> None:
    """다른 소재가 없으면 브이로그로 분류된다."""
    result = classifier.classify("자취생 평일 일상 브이로그")

    assert result.parent == "vlog"


def test_classify_more_matches_beats_weight(classifier: KeywordClassifier) -> None:
    """키워드가 여러 개 걸리면 가중치 차이를 넘어선다 (근거의 양이 우선)."""
    result = classifier.classify("맛집 먹방 요리 레시피 백반 — AI 추천")

    assert result.parent == "food"


def test_classify_combines_title_and_tags(classifier: KeywordClassifier) -> None:
    """제목·태그·설명을 함께 본다 (FR-1)."""
    result = classifier.classify("3일차 기록", tags=["헬스", "다이어트"], description="오늘 운동 루틴")

    assert result.parent == "fitness"


def test_classify_is_case_insensitive_for_ascii(classifier: KeywordClassifier) -> None:
    """영문 키워드는 대소문자를 가리지 않는다 (chatgpt = ChatGPT)."""
    assert classifier.classify("chatgpt 활용법").parent == "aicoding"
    assert classifier.classify("CHATGPT 활용법").parent == "aicoding"


def test_classify_records_matched_keywords(classifier: KeywordClassifier) -> None:
    """어떤 키워드로 분류됐는지 남긴다 — 미분류율 점검·튜닝 근거 (FR-9)."""
    result = classifier.classify("도쿄 맛집 먹방")

    assert "맛집" in result.matched_keywords
    assert "도쿄" in result.matched_tag_keywords


def test_classify_empty_text_is_unclassified(classifier: KeywordClassifier) -> None:
    """빈 입력은 미분류다 (예외를 던지지 않는다 — 수집 중단 방지, NFR-7)."""
    result = classifier.classify("")

    assert result.unclassified is True
    assert isinstance(result, Classification)


def test_unclassified_rate_helper(classifier: KeywordClassifier) -> None:
    """미분류율 계산 — admin 리포트의 LLM 도입 트리거 지표 (D10)."""
    results = [
        classifier.classify("맛집 먹방"),
        classifier.classify("헬스 운동"),
        classifier.classify("알 수 없는 제목"),
        classifier.classify("여전히 알 수 없음"),
    ]

    assert KeywordClassifier.unclassified_rate(results) == pytest.approx(0.5)


def test_unclassified_rate_empty_is_zero(classifier: KeywordClassifier) -> None:
    """수집 결과가 0건이면 미분류율은 0으로 본다 (0 나눗셈 방지)."""
    assert KeywordClassifier.unclassified_rate([]) == 0.0

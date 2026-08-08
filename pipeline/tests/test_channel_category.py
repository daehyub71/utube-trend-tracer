"""채널 카테고리 확정 테스트 (D9 이월 과제).

채널 설명 기반 판정의 오탐을 피하려고 영상 분포로 정한다.
"""

from app.channel_category import dominant_parent, resolve_channel_category


def test_uses_most_common_category() -> None:
    """영상 다수가 해외 소재면 채널도 해외로 본다."""
    categories = ["travel_overseas"] * 7 + ["travel_domestic"] * 2

    assert resolve_channel_category(categories) == "travel_overseas"


def test_domestic_channel_stays_domestic() -> None:
    categories = ["food_domestic"] * 8 + ["food_overseas"]

    assert resolve_channel_category(categories) == "food_domestic"


def test_falls_back_to_parent_with_default_tag() -> None:
    """영상 근거가 없으면 시드에 기록한 대분류 + 기본 태그(국내)로 둔다."""
    assert resolve_channel_category([], fallback_parent="fitness") == "fitness_domestic"


def test_returns_none_without_any_evidence() -> None:
    assert resolve_channel_category([]) is None


def test_single_video_still_yields_a_category() -> None:
    """근거가 적어도 있는 것은 쓴다 — 콜드스타트 초기에 보드가 비지 않게."""
    assert resolve_channel_category(["tech_domestic"]) == "tech_domestic"


def test_dominant_parent_ignores_tag() -> None:
    """대분류만 볼 때는 태그를 무시한다."""
    categories = ["food_domestic", "food_overseas", "travel_domestic"]

    assert dominant_parent(categories) == "food"


def test_dominant_parent_without_evidence_is_none() -> None:
    assert dominant_parent([]) is None

"""쿼터 예산 트래커 테스트 (NFR-4, D14).

쿼터가 바닥나면 수집만 멈추고 서빙은 계속돼야 한다 (서비스 다운이 아니다).
"예산을 넘었는지"를 호출 전에 묻고, 넘으면 그 호출을 하지 않는 것이 규약이다.
"""

import pytest

from app.quota import QuotaBudget, QuotaExceeded

DAILY_LIMIT = 10_000


def test_starts_empty() -> None:
    budget = QuotaBudget(daily_limit=DAILY_LIMIT)

    assert budget.used == 0
    assert budget.remaining == DAILY_LIMIT


def test_spend_accumulates() -> None:
    budget = QuotaBudget(daily_limit=DAILY_LIMIT)

    budget.spend(100)
    budget.spend(1)

    assert budget.used == 101
    assert budget.remaining == DAILY_LIMIT - 101


def test_can_afford_checks_before_call() -> None:
    """호출 전에 물어본다 — 넘고 나서 되돌릴 수 없기 때문."""
    budget = QuotaBudget(daily_limit=150)

    assert budget.can_afford(100) is True
    budget.spend(100)
    assert budget.can_afford(100) is False
    assert budget.can_afford(50) is True


def test_spend_beyond_limit_raises() -> None:
    """예산을 넘기는 지출은 예외로 막는다 (조용한 초과 금지)."""
    budget = QuotaBudget(daily_limit=100)

    with pytest.raises(QuotaExceeded):
        budget.spend(101)


def test_resume_from_prior_usage() -> None:
    """하루 안에 여러 번 실행되므로 기존 사용량에서 이어 쓴다 (cron 3회)."""
    budget = QuotaBudget(daily_limit=DAILY_LIMIT, used=7_000)

    assert budget.remaining == 3_000
    assert budget.can_afford(2_000) is True
    assert budget.can_afford(4_000) is False


def test_reserve_leaves_headroom_for_essential_calls() -> None:
    """발굴(search)은 예약분을 침범하지 않는다 — 스냅샷 수집이 우선이다."""
    budget = QuotaBudget(daily_limit=1_000, reserve=300)

    assert budget.can_afford(700, respect_reserve=True) is True
    assert budget.can_afford(701, respect_reserve=True) is False
    # 예약분은 필수 호출에는 열려 있다.
    assert budget.can_afford(900, respect_reserve=False) is True


def test_search_budget_follows_spec() -> None:
    """D14: 초기 2주 60회/일(6,000유닛) → 이후 20회/일(2,000유닛)."""
    assert QuotaBudget.search_budget(days_since_start=3) == 6_000
    assert QuotaBudget.search_budget(days_since_start=13) == 6_000
    assert QuotaBudget.search_budget(days_since_start=14) == 2_000
    assert QuotaBudget.search_budget(days_since_start=60) == 2_000


def test_exhausted_flag() -> None:
    budget = QuotaBudget(daily_limit=100)
    assert budget.exhausted is False

    budget.spend(100)
    assert budget.exhausted is True

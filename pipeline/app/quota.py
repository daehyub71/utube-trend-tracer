"""쿼터 예산 관리 (NFR-4, D14).

일 10,000유닛을 넘기면 다음 날까지 수집이 막힌다. 그래서 "쓰고 나서 확인"이 아니라
"호출 전에 물어보고, 안 되면 그 호출을 건너뛴다"가 규약이다.
쿼터가 바닥나도 서빙은 영향받지 않는다 — 수집만 멈춘다.
"""

from __future__ import annotations

from dataclasses import dataclass

DAILY_QUOTA_LIMIT = 10_000

# 발굴(search)이 침범하면 안 되는 예약분 — 스냅샷 수집이 우선이다.
DEFAULT_RESERVE = 2_000

# D14: 초기 2주는 발굴에 예산을 집중하고, 이후 줄인다.
BOOTSTRAP_DAYS = 14
BOOTSTRAP_SEARCH_BUDGET = 6_000
STEADY_SEARCH_BUDGET = 2_000


class QuotaExceeded(RuntimeError):
    """예산을 넘기는 지출을 시도한 경우."""


@dataclass
class QuotaBudget:
    """하루치 쿼터 예산.

    Attributes:
        daily_limit: 하루 한도 (기본 10,000유닛).
        used: 이미 사용한 유닛 — 하루 안에 여러 번 실행되므로 이어서 쓴다.
        reserve: 필수 호출용으로 남겨두는 유닛.
    """

    daily_limit: int = DAILY_QUOTA_LIMIT
    used: int = 0
    reserve: int = DEFAULT_RESERVE

    @property
    def remaining(self) -> int:
        """남은 유닛."""
        return max(0, self.daily_limit - self.used)

    @property
    def exhausted(self) -> bool:
        """예산이 바닥났는지 여부."""
        return self.remaining <= 0

    def can_afford(self, cost: int, *, respect_reserve: bool = False) -> bool:
        """이 비용을 지출할 여유가 있는지 확인한다.

        Args:
            cost: 지출하려는 유닛.
            respect_reserve: True면 예약분을 침범하지 않는 범위에서만 허용한다
                (발굴처럼 미룰 수 있는 호출에 쓴다).

        Returns:
            지출 가능 여부.
        """
        available = self.remaining - (self.reserve if respect_reserve else 0)
        return cost <= available

    def spend(self, cost: int) -> None:
        """유닛을 사용 처리한다.

        Args:
            cost: 사용한 유닛.

        Raises:
            QuotaExceeded: 한도를 넘기는 경우.
        """
        if self.used + cost > self.daily_limit:
            raise QuotaExceeded(
                f"쿼터 초과: {self.used} + {cost} > {self.daily_limit}. 이번 주기 수집을 중단합니다."
            )
        self.used += cost

    @staticmethod
    def search_budget(days_since_start: int) -> int:
        """운영 경과일에 따른 발굴 예산을 돌려준다 (D14).

        Args:
            days_since_start: 수집 시작 이후 경과일.

        Returns:
            그날 발굴에 쓸 수 있는 유닛.
        """
        return BOOTSTRAP_SEARCH_BUDGET if days_since_start < BOOTSTRAP_DAYS else STEADY_SEARCH_BUDGET

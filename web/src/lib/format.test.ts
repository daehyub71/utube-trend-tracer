import { describe, expect, it } from "vitest";

import { formatBasisTime, formatCount, formatGrowth, formatRelativeDay, formatScore } from "./format";

describe("formatCount", () => {
  it("만 단위 미만은 천 단위 구분자로 표시한다", () => {
    expect(formatCount(8200)).toBe("8,200");
    expect(formatCount(0)).toBe("0");
  });

  it("만 단위 이상은 '만'으로 축약한다", () => {
    expect(formatCount(12300)).toBe("1.2만");
    expect(formatCount(342100)).toBe("34.2만");
  });

  it("소수점이 0이면 생략한다", () => {
    expect(formatCount(510000)).toBe("51만");
  });

  it("값이 없으면 대시로 표시한다", () => {
    expect(formatCount(null)).toBe("—");
  });
});

describe("formatScore", () => {
  it("자체 산출 점수를 0~100 정수로 보여준다", () => {
    // 점수는 카테고리 내 최고점 대비 상대값으로 환산한다.
    expect(formatScore(0.5, 0.5)).toBe(100);
    expect(formatScore(0.25, 0.5)).toBe(50);
  });

  it("최고점이 0이면 0을 돌려준다 (0 나눗셈 방지)", () => {
    expect(formatScore(0, 0)).toBe(0);
  });

  it("아주 작은 점수도 최소 1로 보여준다 (0은 랭킹에 오르지 않는다)", () => {
    expect(formatScore(0.0001, 100)).toBe(1);
  });
});

describe("formatGrowth", () => {
  it("성장률을 백분율로 표시한다", () => {
    expect(formatGrowth(0.136)).toBe("+13.6%");
    expect(formatGrowth(2.1)).toBe("+210%");
  });

  it("100% 이상은 소수점을 생략한다", () => {
    expect(formatGrowth(0.88)).toBe("+88.0%");
    expect(formatGrowth(1.5)).toBe("+150%");
  });

  it("값이 없으면 대시로 표시한다", () => {
    expect(formatGrowth(null)).toBe("—");
  });
});

describe("formatRelativeDay", () => {
  const now = new Date("2026-08-08T12:00:00Z");

  it("24시간 이내는 시간 단위로 표시한다", () => {
    expect(formatRelativeDay("2026-08-08T09:00:00Z", now)).toBe("3시간 전");
  });

  it("1시간 이내는 '방금 전'", () => {
    expect(formatRelativeDay("2026-08-08T11:40:00Z", now)).toBe("방금 전");
  });

  it("하루가 지나면 일 단위로 표시한다", () => {
    expect(formatRelativeDay("2026-08-06T12:00:00Z", now)).toBe("2일 전");
  });

  it("잘못된 값은 빈 문자열", () => {
    expect(formatRelativeDay("nonsense", now)).toBe("");
  });
});

describe("formatBasisTime", () => {
  it("산출 기준 시각을 한국 시간으로 표시한다 (NFR-2의 짝)", () => {
    // 2026-08-08T05:00:00Z = KST 14:00
    expect(formatBasisTime("2026-08-08T05:00:00Z")).toBe("오늘 14:00 기준");
  });

  it("아직 산출 전이면 안내 문구를 돌려준다", () => {
    expect(formatBasisTime(null)).toBe("아직 집계 전");
  });
});

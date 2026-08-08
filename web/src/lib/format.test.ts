import { describe, expect, it } from "vitest";

import { formatCount } from "./format";

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
});

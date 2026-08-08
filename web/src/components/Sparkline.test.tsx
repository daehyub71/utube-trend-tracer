import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { SeriesPoint } from "@/lib/types";

import { Sparkline, buildPath } from "./Sparkline";

function series(values: number[]): SeriesPoint[] {
  return values.map((value, index) => ({
    capturedAt: new Date(Date.UTC(2026, 7, index + 1)).toISOString(),
    value,
  }));
}

describe("buildPath", () => {
  it("점 개수만큼 좌표를 만든다", () => {
    const path = buildPath(series([1, 2, 3]), 300, 80);

    expect(path.split("L")).toHaveLength(3); // M + L + L
  });

  it("최댓값은 위, 최솟값은 아래에 온다", () => {
    const path = buildPath(series([10, 20]), 100, 100);
    const [first, second] = path.replace("M", "").split("L").map((p) => Number(p.split(",")[1]));

    expect(second).toBeLessThan(first); // y가 작을수록 위
  });

  it("모든 값이 같으면 평평한 선을 그린다 (0 나눗셈 방지)", () => {
    const path = buildPath(series([5, 5, 5]), 100, 100);
    const ys = path.replace("M", "").split("L").map((p) => Number(p.split(",")[1]));

    expect(new Set(ys).size).toBe(1);
    expect(ys.every((y) => Number.isFinite(y))).toBe(true);
  });

  it("점이 없으면 빈 경로", () => {
    expect(buildPath([], 100, 100)).toBe("");
  });
});

describe("Sparkline", () => {
  it("제목과 최신값을 보여준다", () => {
    render(<Sparkline title="구독자 (30일)" points={series([100, 200, 342100])} />);

    expect(screen.getByText("구독자 (30일)")).toBeInTheDocument();
    expect(screen.getByText("342,100")).toBeInTheDocument();
  });

  it("데이터가 부족하면 안내를 보여준다 (콜드스타트)", () => {
    render(<Sparkline title="구독자 (30일)" points={series([100])} />);

    expect(screen.getByText(/집계/)).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("접근성 라벨을 붙인다", () => {
    render(<Sparkline title="구독자 (30일)" points={series([1, 2, 3])} />);

    expect(screen.getByRole("img", { name: /구독자/ })).toBeInTheDocument();
  });
});

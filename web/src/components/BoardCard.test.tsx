import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { BoardEntry, BoardResult } from "@/lib/types";

import { BoardCard } from "./BoardCard";

function videoEntry(rank: number, title: string, score = 0.5): BoardEntry {
  return {
    rank,
    score,
    entityId: `vid${rank}`,
    video: {
      title,
      thumbnailUrl: null,
      publishedAt: new Date().toISOString(),
      isShort: false,
      channelId: "UC1",
      channelTitle: "테스트 채널",
      viewCount: 12_345,
      subscriberCount: 50_000,
    },
  };
}

function result(overrides: Partial<BoardResult> = {}): BoardResult {
  return {
    board: "trending_videos",
    entries: [videoEntry(1, "첫 번째 영상"), videoEntry(2, "두 번째 영상", 0.25)],
    computedAt: "2026-08-08T05:00:00Z",
    error: null,
    ...overrides,
  };
}

describe("BoardCard", () => {
  it("보드 제목과 순위를 보여준다", () => {
    render(<BoardCard result={result()} />);

    expect(screen.getByText("지금 뜨는 영상")).toBeInTheDocument();
    expect(screen.getByText("첫 번째 영상")).toBeInTheDocument();
    expect(screen.getByText("두 번째 영상")).toBeInTheDocument();
  });

  it("영상 행은 유튜브로 연결한다 (NFR-1: 재생은 유튜브에서)", () => {
    render(<BoardCard result={result()} />);

    const link = screen.getByRole("link", { name: /첫 번째 영상/ });
    expect(link).toHaveAttribute("href", "https://www.youtube.com/watch?v=vid1");
  });

  it("콜드스타트에는 집계 중 안내를 보여주고 보드는 유지한다", () => {
    render(<BoardCard result={result({ entries: [], computedAt: null })} />);

    expect(screen.getByText("지금 뜨는 영상")).toBeInTheDocument();
    expect(screen.getByText(/집계/)).toBeInTheDocument();
  });

  it("조회 실패는 그 보드에만 표시한다 (화면 전체가 죽지 않게)", () => {
    render(<BoardCard result={result({ entries: [], error: "랭킹을 불러오지 못했습니다." })} />);

    expect(screen.getByText("랭킹을 불러오지 못했습니다.")).toBeInTheDocument();
  });

  it("기본 5행만 보여주고 나머지는 접는다 (DESIGN DQ4)", () => {
    const many = Array.from({ length: 12 }, (_, i) => videoEntry(i + 1, `영상 ${i + 1}`, 1 - i * 0.05));
    render(<BoardCard result={result({ entries: many })} />);

    expect(screen.getByText("영상 5")).toBeInTheDocument();
    expect(screen.queryByText("영상 6")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /더 보기/ })).toBeInTheDocument();
  });

  it("항목이 5개 이하면 더 보기 버튼이 없다", () => {
    render(<BoardCard result={result()} />);

    expect(screen.queryByRole("button", { name: /더 보기/ })).not.toBeInTheDocument();
  });

  it("Shorts는 표시로 구분한다 (β 보정 대상, D8)", () => {
    const short = videoEntry(1, "쇼츠 영상");
    short.video!.isShort = true;
    render(<BoardCard result={result({ entries: [short] })} />);

    expect(screen.getByText("Shorts")).toBeInTheDocument();
  });

  it("채널 보드는 성장률로 표기한다 (DESIGN DQ3)", () => {
    const channelResult: BoardResult = {
      board: "rising_channels",
      entries: [
        {
          rank: 1,
          score: 0.9,
          entityId: "UCx",
          channel: {
            title: "성장 채널",
            thumbnailUrl: null,
            subscriberCount: 8_200,
            growthRate: 2.1,
          },
        },
      ],
      computedAt: "2026-08-08T05:00:00Z",
      error: null,
    };

    render(<BoardCard result={channelResult} />);

    expect(screen.getByText("+210%")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /성장 채널/ })).toHaveAttribute(
      "href",
      "/channel/UCx"
    );
  });
});

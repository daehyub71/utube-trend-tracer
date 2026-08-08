import { Suspense } from "react";

import { BoardCard } from "@/components/BoardCard";
import { CategoryPicker } from "@/components/CategoryPicker";
import { formatBasisTime } from "@/lib/format";
import { fetchBoards, fetchCategories } from "@/lib/queries";
import type { BoardId } from "@/lib/types";

const BOARDS: BoardId[] = [
  "trending_videos",
  "rising_videos",
  "trending_channels",
  "rising_channels",
];

const DEFAULT_PARENT = "food";

// 랭킹은 수집 주기(하루 3회)에만 바뀐다 — 10분 캐시로 DB 조회를 아낀다.
export const revalidate = 600;

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ c?: string; t?: string }>;
}) {
  const params = await searchParams;
  const categories = await fetchCategories();

  const parents = [...new Set(categories.map((c) => c.parent))];
  const parent = params.c && parents.includes(params.c) ? params.c : (parents[0] ?? DEFAULT_PARENT);
  const tag = params.t === "domestic" || params.t === "overseas" ? params.t : "all";

  // '전체'는 국내 카테고리를 기본으로 보여준다 — 대부분의 소재가 국내이기 때문.
  const categoryId = `${parent}_${tag === "overseas" ? "overseas" : "domestic"}`;
  const results = await fetchBoards(categoryId, BOARDS);
  const basis = results.find((r) => r.computedAt)?.computedAt ?? null;

  return (
    <div className="flex flex-col gap-4">
      <Suspense fallback={<div className="h-9" />}>
        <CategoryPicker categories={categories} selectedParent={parent} selectedTag={tag} />
      </Suspense>

      <p className="px-1 text-xs text-ink-3">
        {formatBasisTime(basis)} · 트렌드 점수는 유튜브 공식 지표가 아닌 자체 산출값입니다 · 데이터
        출처: YouTube
      </p>

      <div className="grid gap-4 md:grid-cols-2">
        {results.map((result) => (
          <BoardCard key={result.board} result={result} />
        ))}
      </div>
    </div>
  );
}

"use client";

import { useRouter, useSearchParams } from "next/navigation";

import type { Category } from "@/lib/types";

type TagFilter = "all" | "domestic" | "overseas";

const TAG_LABELS: Record<TagFilter, string> = {
  all: "전체",
  domestic: "국내",
  overseas: "해외",
};

/**
 * 대분류 칩 + 국내/해외 세그먼트.
 *
 * 선택 상태는 URL 쿼리에 담는다 — 링크를 공유하면 같은 화면이 열려야 한다.
 */
export function CategoryPicker({
  categories,
  selectedParent,
  selectedTag,
}: {
  categories: Category[];
  selectedParent: string;
  selectedTag: TagFilter;
}) {
  const router = useRouter();
  const params = useSearchParams();

  const parents = dedupeParents(categories);

  function navigate(next: { parent?: string; tag?: TagFilter }) {
    const query = new URLSearchParams(params.toString());
    if (next.parent) query.set("c", next.parent);
    if (next.tag) query.set("t", next.tag);
    router.push(`/?${query.toString()}`, { scroll: false });
  }

  return (
    <div className="flex flex-wrap items-center gap-2 px-1">
      <div className="flex flex-1 flex-wrap gap-2">
        {parents.map((parent) => {
          const active = parent.id === selectedParent;
          return (
            <button
              key={parent.id}
              type="button"
              aria-pressed={active}
              onClick={() => navigate({ parent: parent.id })}
              className={`rounded-full border px-3.5 py-1.5 text-[13px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
                active
                  ? "border-accent bg-accent text-white"
                  : "border-line bg-surface text-ink-2 hover:border-accent hover:text-accent-ink"
              }`}
            >
              {parent.label}
            </button>
          );
        })}
      </div>

      <div className="flex overflow-hidden rounded-lg border border-line">
        {(Object.keys(TAG_LABELS) as TagFilter[]).map((tag) => {
          const active = tag === selectedTag;
          return (
            <button
              key={tag}
              type="button"
              aria-pressed={active}
              onClick={() => navigate({ tag })}
              className={`px-3 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
                active ? "bg-accent-tint text-accent-ink" : "text-ink-2 hover:bg-surface-2"
              }`}
            >
              {TAG_LABELS[tag]}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** 카테고리 목록(대분류 × 태그)에서 대분류만 뽑는다. */
function dedupeParents(categories: Category[]): { id: string; label: string }[] {
  const seen = new Map<string, string>();
  for (const category of categories) {
    if (!seen.has(category.parent)) {
      // 이름은 "음식 > 국내" 형태이므로 대분류 부분만 쓴다.
      seen.set(category.parent, category.name.split(" > ")[0] ?? category.parent);
    }
  }
  return [...seen].map(([id, label]) => ({ id, label }));
}

"use client";

import Link from "next/link";
import { useState } from "react";

import { formatCount, formatGrowth, formatRelativeDay, formatScore } from "@/lib/format";
import type { BoardEntry, BoardResult } from "@/lib/types";
import { BOARD_META, VIDEO_BOARDS } from "@/lib/types";

const DEFAULT_ROWS = 5;

/**
 * 랭킹 보드 하나.
 *
 * 항목이 없어도 보드는 남긴다 — 콜드스타트나 수집 공백에 보드가 사라지면
 * 레이아웃이 무너지고, 사용자는 무엇이 비었는지 알 수 없다 (DESIGN §5).
 */
export function BoardCard({ result }: { result: BoardResult }) {
  const [expanded, setExpanded] = useState(false);
  const meta = BOARD_META[result.board];
  const isVideoBoard = VIDEO_BOARDS.includes(result.board);

  const visible = expanded ? result.entries : result.entries.slice(0, DEFAULT_ROWS);
  const hidden = result.entries.length - visible.length;
  const maxScore = result.entries[0]?.score ?? 0;

  return (
    <section className="overflow-hidden rounded-xl border border-line bg-surface">
      <header className="flex items-baseline gap-2 px-4 pt-4 pb-2.5">
        <span
          aria-hidden
          className={`size-2 self-center rounded-sm ${
            meta.tone === "heat" ? "bg-heat" : "bg-accent"
          }`}
        />
        <h2 className="text-[15px] font-extrabold tracking-tight">{meta.title}</h2>
        <span className="ml-auto text-[11px] text-ink-3">{meta.hint}</span>
      </header>

      {result.error ? (
        <p className="border-t border-line px-4 py-6 text-center text-sm text-ink-2">
          {result.error}
        </p>
      ) : result.entries.length === 0 ? (
        <p className="border-t border-line px-4 py-6 text-center text-sm text-ink-2">
          아직 집계 중입니다 · 순위는 데이터가 이틀 이상 쌓인 뒤 나타납니다
        </p>
      ) : (
        <>
          <ul className="border-t border-line">
            {visible.map((entry) => (
              <li key={entry.entityId} className="border-b border-line last:border-b-0">
                {isVideoBoard ? (
                  <VideoRow entry={entry} maxScore={maxScore} />
                ) : (
                  <ChannelRow entry={entry} />
                )}
              </li>
            ))}
          </ul>
          {hidden > 0 && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="w-full border-t border-line px-4 py-2.5 text-xs font-semibold text-accent-ink hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-accent"
            >
              더 보기 ({hidden}개)
            </button>
          )}
        </>
      )}
    </section>
  );
}

function VideoRow({ entry, maxScore }: { entry: BoardEntry; maxScore: number }) {
  const video = entry.video;
  if (!video) return null;

  return (
    <a
      href={`https://www.youtube.com/watch?v=${encodeURIComponent(entry.entityId)}`}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-accent"
    >
      <span
        className={`tabular w-4 text-[13px] font-extrabold ${
          entry.rank <= 2 ? "text-accent-ink" : "text-ink-3"
        }`}
      >
        {entry.rank}
      </span>
      <span className="relative shrink-0">
        {video.thumbnailUrl ? (
          // 썸네일은 YouTube CDN에서 그대로 가져온다 (재호스팅하지 않는다, NFR-1).
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={video.thumbnailUrl}
            alt=""
            className="h-11 w-[78px] rounded-md object-cover"
            loading="lazy"
          />
        ) : (
          <span className="grid h-11 w-[78px] place-items-center rounded-md bg-surface-2 text-[11px] text-ink-3">
            ▶
          </span>
        )}
        {video.isShort && (
          <span className="absolute bottom-0.5 right-0.5 rounded bg-ink/75 px-1 text-[9px] font-bold text-white">
            Shorts
          </span>
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold">{video.title}</span>
        <span className="tabular block text-xs text-ink-2">
          {video.channelTitle} · 조회 {formatCount(video.viewCount)} ·{" "}
          {formatRelativeDay(video.publishedAt)}
        </span>
      </span>
      <span className="tabular shrink-0 rounded-md bg-heat-tint px-2 py-1 text-xs font-extrabold text-heat">
        ▲ {formatScore(entry.score, maxScore)}
      </span>
    </a>
  );
}

function ChannelRow({ entry }: { entry: BoardEntry }) {
  const channel = entry.channel;
  if (!channel) return null;

  return (
    <Link
      href={`/channel/${entry.entityId}`}
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-accent"
    >
      <span
        className={`tabular w-4 text-[13px] font-extrabold ${
          entry.rank <= 2 ? "text-accent-ink" : "text-ink-3"
        }`}
      >
        {entry.rank}
      </span>
      {channel.thumbnailUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={channel.thumbnailUrl} alt="" className="size-10 shrink-0 rounded-full" loading="lazy" />
      ) : (
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-tint text-sm font-extrabold text-accent-ink">
          {channel.title.slice(0, 1)}
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold">{channel.title}</span>
        <span className="tabular block text-xs text-ink-2">
          구독 {formatCount(channel.subscriberCount)}
        </span>
      </span>
      <span className="tabular shrink-0 rounded-md bg-accent-tint px-2 py-1 text-xs font-extrabold text-accent-ink">
        {formatGrowth(channel.growthRate)}
      </span>
    </Link>
  );
}

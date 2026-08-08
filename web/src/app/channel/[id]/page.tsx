import Link from "next/link";
import { notFound } from "next/navigation";

import { Sparkline } from "@/components/Sparkline";
import { formatCount, formatRelativeDay } from "@/lib/format";
import { fetchChannelDetail } from "@/lib/queries";

export const revalidate = 600;

export default async function ChannelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const channel = await fetchChannelDetail(id);
  if (!channel) notFound();

  const viewDelta = deltaLabel(channel.viewSeries.map((p) => p.value));

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-center gap-4">
        {channel.thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={channel.thumbnailUrl} alt="" className="size-14 rounded-full" />
        ) : (
          <span className="grid size-14 place-items-center rounded-full bg-accent-tint text-xl font-extrabold text-accent-ink">
            {channel.title.slice(0, 1)}
          </span>
        )}
        <div className="min-w-0">
          <h1 className="truncate text-xl font-extrabold tracking-tight">{channel.title}</h1>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {channel.categoryIds.map((categoryId) => (
              <span
                key={categoryId}
                className="rounded bg-accent-tint px-2 py-0.5 text-[11px] font-bold text-accent-ink"
              >
                {categoryId}
              </span>
            ))}
          </div>
        </div>
        <div className="ml-auto text-right">
          <p className="tabular text-xl font-extrabold">{formatCount(channel.subscriberCount)}</p>
          <p className="text-[11px] text-ink-3">구독자</p>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <Sparkline title="구독자 (30일)" points={channel.subscriberSeries} />
        <Sparkline title="총 조회수 (30일)" points={channel.viewSeries} caption={viewDelta} />
      </div>

      <section>
        <h2 className="mb-2 text-[13px] font-extrabold">최근 영상</h2>
        {channel.recentVideos.length === 0 ? (
          <p className="rounded-xl border border-line bg-surface px-4 py-6 text-center text-sm text-ink-2">
            아직 수집된 영상이 없습니다
          </p>
        ) : (
          <ul className="overflow-hidden rounded-xl border border-line bg-surface">
            {channel.recentVideos.map((entry) => (
              <li key={entry.entityId} className="border-b border-line last:border-b-0">
                <a
                  href={`https://www.youtube.com/watch?v=${entry.entityId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 px-4 py-2.5 hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-accent"
                >
                  {entry.video?.thumbnailUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={entry.video.thumbnailUrl}
                      alt=""
                      className="h-11 w-[78px] shrink-0 rounded-md object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <span className="grid h-11 w-[78px] shrink-0 place-items-center rounded-md bg-surface-2 text-[11px] text-ink-3">
                      ▶
                    </span>
                  )}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold">
                      {entry.video?.title}
                    </span>
                    <span className="tabular block text-xs text-ink-2">
                      조회 {formatCount(entry.video?.viewCount)} ·{" "}
                      {formatRelativeDay(entry.video?.publishedAt ?? "")}
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Link href="/" className="text-[13px] text-accent-ink hover:underline">
        ← 랭킹으로 돌아가기
      </Link>
    </div>
  );
}

/** 30일 구간의 증감을 짧게 표시한다. */
function deltaLabel(values: number[]): string | undefined {
  if (values.length < 2) return undefined;
  const first = values[0];
  const last = values.at(-1)!;
  if (first <= 0) return undefined;
  const rate = ((last - first) / first) * 100;
  return rate >= 0.1 ? `+${rate.toFixed(1)}%` : undefined;
}

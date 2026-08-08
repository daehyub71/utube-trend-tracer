import type { SeriesPoint } from "@/lib/types";

const WIDTH = 320;
const HEIGHT = 84;
const PAD_X = 4;
const PAD_Y = 12;

/**
 * 30일 추이 미니 차트.
 *
 * 구독자와 조회수는 스케일이 달라 한 축에 겹치지 않는다 — 각각 단일 시리즈로
 * 나란히 둔다 (DESIGN §2, 이중축 금지).
 */
export function Sparkline({
  title,
  points,
  caption,
}: {
  title: string;
  points: SeriesPoint[];
  caption?: string;
}) {
  const latest = points.at(-1)?.value ?? null;

  return (
    <figure className="m-0 rounded-xl border border-line bg-surface px-4 pt-3.5 pb-2">
      <figcaption className="text-xs font-bold text-ink-2">{title}</figcaption>
      <p className="tabular text-lg font-extrabold">
        {latest === null ? "—" : latest.toLocaleString("ko-KR")}
        {caption && <span className="ml-1.5 text-[11px] font-bold text-heat">{caption}</span>}
      </p>

      {points.length < 2 ? (
        <p className="py-4 text-center text-xs text-ink-3">
          아직 집계 중입니다 · 추이는 스냅샷이 쌓이면 나타납니다
        </p>
      ) : (
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`${title} 추이`}
          className="mt-1.5 block h-[84px] w-full"
        >
          {[PAD_Y + 8, HEIGHT / 2, HEIGHT - PAD_Y].map((y) => (
            <line key={y} x1={0} y1={y} x2={WIDTH} y2={y} className="stroke-line" strokeWidth={1} />
          ))}
          <path d={buildAreaPath(points, WIDTH, HEIGHT)} className="fill-accent opacity-[0.12]" />
          <path
            d={buildPath(points, WIDTH, HEIGHT)}
            fill="none"
            className="stroke-accent"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle
            cx={WIDTH - PAD_X}
            cy={yFor(points.at(-1)!.value, points, HEIGHT)}
            r={4}
            className="fill-accent stroke-surface"
            strokeWidth={2}
          />
        </svg>
      )}
    </figure>
  );
}

/** 시계열을 SVG path 문자열로 만든다. */
export function buildPath(points: SeriesPoint[], width: number, height: number): string {
  if (points.length === 0) return "";

  return points
    .map((point, index) => {
      const x = xFor(index, points.length, width);
      const y = yFor(point.value, points, height);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join("");
}

function buildAreaPath(points: SeriesPoint[], width: number, height: number): string {
  const line = buildPath(points, width, height);
  if (!line) return "";
  return `${line}L${(width - PAD_X).toFixed(1)},${height - PAD_Y}L${PAD_X},${height - PAD_Y}Z`;
}

function xFor(index: number, total: number, width: number): number {
  if (total <= 1) return PAD_X;
  return PAD_X + (index / (total - 1)) * (width - PAD_X * 2);
}

function yFor(value: number, points: SeriesPoint[], height: number): number {
  const values = points.map((p) => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  // 값이 모두 같으면 가운데에 평평한 선을 그린다 (0 나눗셈 방지).
  if (span === 0) return height / 2;
  const ratio = (value - min) / span;
  return height - PAD_Y - ratio * (height - PAD_Y * 2);
}

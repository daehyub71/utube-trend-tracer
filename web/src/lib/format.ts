const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

/**
 * 조회수·구독자 수를 한국어 표기로 축약한다.
 *
 * 만 단위 미만은 천 단위 구분자, 만 단위 이상은 소수 첫째 자리까지의 '만' 표기.
 */
export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value < 10_000) return value.toLocaleString("ko-KR");
  const rounded = Math.round((value / 10_000) * 10) / 10;
  return `${rounded}만`;
}

/**
 * 자체 산출 점수를 카테고리 내 최고점 대비 0~100으로 환산한다.
 *
 * 원점수는 산식상 아주 작은 소수라 그대로 보여줄 수 없다 (SPEC FR-7).
 * 랭킹에 오른 항목은 점수가 0보다 크므로 최소 1로 표시한다.
 */
export function formatScore(score: number, maxScore: number): number {
  if (maxScore <= 0) return 0;
  return Math.max(1, Math.round((score / maxScore) * 100));
}

/** 성장률을 백분율 문자열로 만든다 (채널 보드 표기, DESIGN DQ3). */
export function formatGrowth(rate: number | null | undefined): string {
  if (rate === null || rate === undefined) return "—";
  const percent = rate * 100;
  return percent >= 100 ? `+${Math.round(percent)}%` : `+${percent.toFixed(1)}%`;
}

/** 업로드 시점을 '3시간 전' / '2일 전' 형태로 표시한다. */
export function formatRelativeDay(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";

  const hours = (now.getTime() - then.getTime()) / 3_600_000;
  if (hours < 1) return "방금 전";
  if (hours < 24) return `${Math.floor(hours)}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

/**
 * 랭킹 산출 기준 시각을 표시한다.
 *
 * 자체 산출 지표임을 밝히는 문구(NFR-2)와 짝을 이루는 정보다 —
 * 언제 계산된 순위인지 모르면 신뢰할 수 없다.
 */
export function formatBasisTime(iso: string | null): string {
  if (!iso) return "아직 집계 전";
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "아직 집계 전";

  const kst = new Date(at.getTime() + KST_OFFSET_MS);
  const nowKst = new Date(Date.now() + KST_OFFSET_MS);
  const hh = String(kst.getUTCHours()).padStart(2, "0");
  const mm = String(kst.getUTCMinutes()).padStart(2, "0");

  const sameDay =
    kst.getUTCFullYear() === nowKst.getUTCFullYear() &&
    kst.getUTCMonth() === nowKst.getUTCMonth() &&
    kst.getUTCDate() === nowKst.getUTCDate();

  if (sameDay) return `오늘 ${hh}:${mm} 기준`;
  return `${kst.getUTCMonth() + 1}월 ${kst.getUTCDate()}일 ${hh}:${mm} 기준`;
}

/**
 * 조회수·구독자 수를 한국어 표기로 축약한다.
 *
 * 만 단위 미만은 천 단위 구분자, 만 단위 이상은 소수 첫째 자리까지의 '만' 표기.
 */
export function formatCount(value: number): string {
  if (value < 10_000) {
    return value.toLocaleString("ko-KR");
  }
  const inTenThousands = value / 10_000;
  const rounded = Math.round(inTenThousands * 10) / 10;
  return `${rounded}만`;
}

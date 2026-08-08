import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "소개·정책 — 트렌드 트레이서",
  description: "트렌드 점수 산출 방식, 개인정보처리방침, 채널 제외 요청 안내.",
};

// 문의 창구 (D12) — 채널 소유자의 제외 요청을 받는다.
const CONTACT_EMAIL = "skdaehyub@gmail.com";

export default function AboutPage() {
  return (
    <article className="flex max-w-[68ch] flex-col gap-8">
      <header>
        <h1 className="text-2xl font-extrabold tracking-tight">소개·정책</h1>
        <p className="mt-2 text-ink-2">
          유튜브가 2025년 7월 공식 인기 급상승 페이지를 없앤 뒤, 카테고리별로 &ldquo;요즘 뜨는
          것&rdquo;을 찾을 곳이 마땅치 않아졌습니다. 이 서비스는 그 자리를 채웁니다.
        </p>
      </header>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-extrabold">트렌드 점수는 자체 산출값입니다</h2>
        <p className="text-ink-2">
          여기 보이는 순위는 <strong>유튜브가 제공하는 공식 지표가 아닙니다.</strong> 유튜브는
          카테고리별 트렌드를 알려주지 않기 때문에, 채널과 영상의 지표를 주기적으로 기록해 직접
          계산합니다.
        </p>
        <p className="text-ink-2">
          계산 방식은 <strong>일정 시간 동안 얼마나 빠르게 늘었는가</strong>입니다. 누적 조회수가
          많은 영상이 아니라 지금 빠르게 오르는 영상이 위로 옵니다. &ldquo;신규 뜨는&rdquo; 보드는
          여기에 더해 <strong>구독자 규모 대비</strong> 성과를 봅니다 — 그래서 구독자가 적은 채널의
          터진 영상이 대형 채널에 밀리지 않습니다.
        </p>
        <p className="text-ink-2">
          짧은 영상(Shorts)은 조회수가 오르는 속도가 일반 영상과 자릿수가 달라, 같은 기준으로 두면
          순위를 뒤덮습니다. 그래서 보정 계수를 적용해 함께 보여줍니다.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-extrabold">데이터 출처와 보관</h2>
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-ink-2">
          <li>모든 영상·채널 정보는 YouTube에서 가져오며, 재생은 유튜브에서 이뤄집니다.</li>
          <li>수집한 데이터는 30일이 지나면 자동으로 삭제합니다.</li>
          <li>유튜브에서 삭제되거나 비공개로 바뀐 영상은 다음 수집 주기에 이곳에서도 사라집니다.</li>
          <li>연령 제한 영상은 순위에 넣지 않습니다.</li>
        </ul>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-extrabold">개인정보처리방침</h2>
        <p className="text-ink-2">
          이 서비스는 <strong>로그인을 받지 않으며, 방문자의 개인정보를 수집하지 않습니다.</strong>{" "}
          계정도, 쿠키를 통한 추적도 없습니다. 화면에 보이는 채널명·영상 제목·조회수는 유튜브가
          공개하는 정보입니다.
        </p>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-extrabold">채널 제외 요청</h2>
        <p className="text-ink-2">
          채널 운영자가 원하지 않으면 순위에서 빼드립니다. 아래 주소로 채널 주소와 함께 요청해
          주세요. 확인 후 제외하며, 이후 수집에서도 다시 올라오지 않습니다.
        </p>
        <p>
          <a
            href={`mailto:${CONTACT_EMAIL}?subject=채널 제외 요청`}
            className="font-semibold text-accent-ink hover:underline"
          >
            {CONTACT_EMAIL}
          </a>
        </p>
        <p className="text-ink-2">
          부적절한 콘텐츠가 순위에 올라온 경우에도 같은 주소로 알려주시면 조치하겠습니다.
        </p>
      </section>

      <Link href="/" className="text-[13px] text-accent-ink hover:underline">
        ← 랭킹으로 돌아가기
      </Link>
    </article>
  );
}

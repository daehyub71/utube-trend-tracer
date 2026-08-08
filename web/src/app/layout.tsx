import type { Metadata } from "next";

import { SiteHeader } from "@/components/SiteHeader";

import "./globals.css";

export const metadata: Metadata = {
  title: "트렌드 트레이서 — 카테고리별 유튜브 트렌드",
  description:
    "음식·여행·IT·AI·브이로그·운동 카테고리에서 지금 뜨는 영상과 유튜버를 자체 산출 지표로 찾습니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-dvh">
        <SiteHeader />
        <main className="mx-auto max-w-5xl px-4 pb-16">{children}</main>
        <footer className="mx-auto max-w-5xl px-4 pb-10 text-xs text-ink-3">
          트렌드 점수는 유튜브 공식 지표가 아닌 자체 산출값입니다 · 데이터 출처: YouTube
        </footer>
      </body>
    </html>
  );
}

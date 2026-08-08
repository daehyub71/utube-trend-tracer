import Link from "next/link";

import { ThemeToggle } from "./ThemeToggle";

export function SiteHeader() {
  return (
    <header className="mx-auto mb-4 flex max-w-5xl items-center gap-3 px-4 py-3.5">
      <Link href="/" className="flex items-baseline gap-2 text-lg font-extrabold tracking-tight">
        <span className="text-accent">▲</span>
        트렌드 트레이서
      </Link>
      <span className="rounded bg-accent-tint px-2 py-0.5 text-[11px] font-bold text-accent-ink">
        자체 산출 지표
      </span>
      <div className="flex-1" />
      <Link href="/about" className="text-[13px] text-ink-2 hover:text-accent-ink">
        소개·정책
      </Link>
      <ThemeToggle />
    </header>
  );
}

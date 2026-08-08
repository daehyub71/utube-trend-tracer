"use client";

import { useEffect, useState } from "react";

type Theme = "system" | "light" | "dark";

const STORAGE_KEY = "utt-theme";

function readStoredTheme(): Theme {
  if (typeof window === "undefined") return "system";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

/**
 * 라이트/다크 토글 (NFR-6).
 *
 * 기본값은 시스템 설정이다 — 이 상태에서는 root에 아무 표시도 남기지 않고
 * prefers-color-scheme 이 결정하게 둔다.
 */
export function ThemeToggle() {
  // 저장된 선택을 초기값으로 읽는다. 서버 렌더 시에는 window가 없으므로 시스템으로 시작하고,
  // 클라이언트에서 처음 그릴 때 저장값이 반영된다.
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") {
      root.removeAttribute("data-theme");
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      root.setAttribute("data-theme", theme);
      window.localStorage.setItem(STORAGE_KEY, theme);
    }
  }, [theme]);

  function cycle() {
    setTheme((current) => (current === "system" ? "light" : current === "light" ? "dark" : "system"));
  }

  const label = theme === "system" ? "테마: 시스템" : theme === "light" ? "테마: 밝게" : "테마: 어둡게";

  return (
    <button
      type="button"
      onClick={cycle}
      aria-label={label}
      title={label}
      className="grid size-8 place-items-center rounded-lg border border-line text-sm text-ink-2 hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent"
    >
      {theme === "system" ? "◐" : theme === "light" ? "☀" : "☾"}
    </button>
  );
}

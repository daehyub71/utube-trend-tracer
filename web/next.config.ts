import type { NextConfig } from "next";

/**
 * 보안 헤더 (보안 리뷰 2026-08-08).
 *
 * 로그인·쿠키·사용자 입력이 없어 탈취할 세션 자체는 없지만, CSP의 `img-src` 한 줄이
 * 썸네일 호스트를 브라우저 단에서도 묶어준다 — 파이프라인 검증과 이중 방어가 된다.
 */
const CSP = [
  "default-src 'self'",
  "img-src 'self' https://*.ytimg.com https://*.ggpht.com https://*.googleusercontent.com data:",
  // Next.js가 하이드레이션에 인라인 스크립트를 쓴다.
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "connect-src 'self' https://*.supabase.co",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: CSP },
          // 외부 링크(유튜브)로 나갈 때 경로를 넘기지 않는다.
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * 웹 전용 Supabase 클라이언트.
 *
 * anon key만 사용한다 — service key는 파이프라인 전용이며 브라우저 번들에
 * 들어가서는 안 된다 (NFR-3). 읽기 권한은 DB의 RLS 정책이 강제한다.
 *
 * 클라이언트는 **요청 시점에 지연 생성**한다. 모듈 로드 시점에 만들면 환경변수가
 * 빠진 환경(CI 빌드, 설정이 덜 된 배포)에서 `createClient` 가 던지는 예외로
 * 페이지 자체가 죽는다. 조회가 실패하는 것과 앱이 뜨지 않는 것은 다르다 (NFR-9).
 */

let cached: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient | null {
  if (cached) return cached;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) return null;

  cached = createClient(url, anonKey, { auth: { persistSession: false } });
  return cached;
}

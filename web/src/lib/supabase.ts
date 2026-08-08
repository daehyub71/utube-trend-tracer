import { createClient } from "@supabase/supabase-js";

/**
 * 웹 전용 Supabase 클라이언트.
 *
 * anon key만 사용한다 — service key는 파이프라인 전용이며 브라우저 번들에
 * 들어가서는 안 된다 (NFR-3). 읽기 권한은 DB의 RLS 정책이 강제한다.
 */
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: { persistSession: false },
});

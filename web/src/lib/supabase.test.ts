import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * 설정이 없을 때의 동작 테스트.
 *
 * 모듈 로드 시점에 클라이언트를 만들면 환경변수가 없는 환경(CI 빌드, 잘못된 배포)에서
 * 페이지 전체가 죽는다. 조회가 실패하는 것과 앱이 뜨지 않는 것은 다르다 (NFR-9).
 */

const ORIGINAL = { ...process.env };

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  process.env = { ...ORIGINAL };
});

describe("getSupabase", () => {
  it("환경변수가 없으면 예외 대신 null을 돌려준다", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    const { getSupabase } = await import("./supabase");

    expect(getSupabase()).toBeNull();
  });

  it("URL만 있고 키가 없어도 null을 돌려준다", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    const { getSupabase } = await import("./supabase");

    expect(getSupabase()).toBeNull();
  });

  it("설정이 갖춰지면 클라이언트를 만든다", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";

    const { getSupabase } = await import("./supabase");

    expect(getSupabase()).not.toBeNull();
  });

  it("같은 인스턴스를 재사용한다", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://example.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";

    const { getSupabase } = await import("./supabase");

    expect(getSupabase()).toBe(getSupabase());
  });
});

describe("queries without configuration", () => {
  beforeEach(() => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  });

  it("보드 조회는 빈 결과와 오류 문구를 돌려준다 (던지지 않는다)", async () => {
    const { fetchBoard } = await import("./queries");

    const result = await fetchBoard("food_domestic", "trending_videos");

    expect(result.entries).toEqual([]);
    expect(result.error).toBeTruthy();
  });

  it("카테고리 조회는 빈 배열을 돌려준다", async () => {
    const { fetchCategories } = await import("./queries");

    await expect(fetchCategories()).resolves.toEqual([]);
  });

  it("채널 상세는 null을 돌려준다", async () => {
    const { fetchChannelDetail } = await import("./queries");

    await expect(fetchChannelDetail("UCx")).resolves.toBeNull();
  });
});

"""Supabase ut_ 스키마 점검 스크립트 (stdlib 전용, venv 불필요).

utube-trend-tracer/.env 에서 SUPABASE_URL / SUPABASE_SERVICE_KEY / SUPABASE_ANON_KEY 를 읽어
1) 테이블 존재·컬럼 일치 (OpenAPI 스펙)  2) anon 읽기 정책  3) anon 쓰기 차단  을 확인한다.
"""
import json
import os
import ssl
import sys
import urllib.request
import urllib.error
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

# Mac python.org 배포판은 시스템 인증서를 쓰지 않는다 (TASKS.md 트러블슈팅 2026-08-08)
if not os.environ.get("SSL_CERT_FILE"):
    try:
        import certifi

        ssl._create_default_https_context = lambda *a, **kw: ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass

EXPECTED: dict[str, set[str]] = {
    "ut_categories": {"id", "name", "parent", "tag", "keywords", "weight", "enabled", "updated_at"},
    "ut_channels": {"channel_id", "title", "thumbnail_url", "category_ids", "unclassified",
                    "is_seed", "tracked", "graduated_at", "last_upload_at", "first_seen_at"},
    "ut_channel_snapshots": {"id", "channel_id", "captured_at", "subscriber_count", "view_count", "video_count"},
    "ut_videos": {"video_id", "channel_id", "title", "thumbnail_url", "published_at", "duration_s",
                  "is_short", "age_restricted", "category_ids", "unclassified"},
    "ut_video_snapshots": {"id", "video_id", "captured_at", "view_count"},
    "ut_trend_scores": {"id", "board", "category_id", "entity_id", "score", "rank",
                        "computed_at", "window_start", "window_end"},
    "ut_collect_runs": {"run_id", "started_at", "finished_at", "quota_used",
                        "videos_updated", "channels_updated", "errors"},
}
ANON_READABLE = ["ut_categories", "ut_channels", "ut_channel_snapshots",
                 "ut_videos", "ut_video_snapshots", "ut_trend_scores"]


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def req(url: str, key: str, method: str = "GET", body: dict | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> int:
    if not ENV_PATH.exists():
        print(f"FAIL: {ENV_PATH} 없음 — .env.example을 복사해 값을 채워주세요.")
        return 1
    env = load_env(ENV_PATH)
    url = env.get("SUPABASE_URL", "").rstrip("/")
    service = env.get("SUPABASE_SERVICE_KEY", "")
    anon = env.get("SUPABASE_ANON_KEY", "")
    if not url or not service:
        print("FAIL: SUPABASE_URL / SUPABASE_SERVICE_KEY가 .env에 비어 있음.")
        return 1

    failures = 0

    # 1) OpenAPI 스펙으로 테이블·컬럼 확인 (service key)
    status, body = req(f"{url}/rest/v1/", service)
    if status != 200:
        print(f"FAIL: OpenAPI 스펙 조회 실패 (HTTP {status}) — URL/키 확인 필요.")
        return 1
    defs = json.loads(body).get("definitions", {})
    print("== 1. 테이블·컬럼 점검 ==")
    for table, want in EXPECTED.items():
        if table not in defs:
            print(f"  MISSING  {table} — 테이블 없음")
            failures += 1
            continue
        have = set(defs[table].get("properties", {}).keys())
        miss, extra = want - have, have - want
        if miss:
            print(f"  DIFF     {table} — 누락 컬럼: {sorted(miss)}" + (f", 추가 컬럼: {sorted(extra)}" if extra else ""))
            failures += 1
        else:
            note = f" (스키마 외 추가 컬럼: {sorted(extra)})" if extra else ""
            print(f"  OK       {table} ({len(have)}개 컬럼){note}")

    other = [t for t in defs if t.startswith("ut_") and t not in EXPECTED]
    if other:
        print(f"  NOTE     스키마에 없는 ut_ 테이블: {other}")

    # 2) anon 읽기 정책
    print("== 2. anon 읽기 정책 ==")
    if not anon:
        print("  SKIP: SUPABASE_ANON_KEY 없음 — RLS 정책 점검 생략")
    else:
        for table in ANON_READABLE:
            status, _ = req(f"{url}/rest/v1/{table}?select=*&limit=1", anon)
            if status == 200:
                print(f"  OK       {table} — anon 읽기 가능")
            else:
                print(f"  FAIL     {table} — anon 읽기 불가 (HTTP {status})")
                failures += 1

        # 3) anon 쓰기 차단 확인 (RLS가 켜져 있으면 거부되어야 정상)
        print("== 3. anon 쓰기 차단 ==")
        status, _ = req(f"{url}/rest/v1/ut_collect_runs", anon, method="POST", body={"quota_used": 0})
        if status in (401, 403):
            print(f"  OK       ut_collect_runs — anon 쓰기 거부 (HTTP {status})")
        else:
            print(f"  FAIL     ut_collect_runs — anon 쓰기가 거부되지 않음 (HTTP {status}) ← RLS 확인 필요")
            failures += 1

    print(f"\n결과: {'전체 통과 ✅' if failures == 0 else f'{failures}건 실패 ❌'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

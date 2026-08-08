"""YouTube Data API v3 키 점검 (stdlib 전용, 쿼터 소모 최소).

1) videos.list (1유닛) — 키 유효성·API 활성화 확인
2) channels.list (1유닛) — 채널 통계 조회 확인 (수집기 핵심 호출)
총 2유닛만 사용한다. 키 값은 출력하지 않는다.
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


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def call(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def main() -> int:
    key = load_env(ENV_PATH).get("YOUTUBE_API_KEY", "")
    if not key:
        print("FAIL: YOUTUBE_API_KEY가 .env에 비어 있음.")
        return 1

    base = "https://www.googleapis.com/youtube/v3"
    failures = 0

    # 1) videos.list — 공개 영상 1건 (1유닛)
    status, body = call(f"{base}/videos?part=snippet,statistics,contentDetails&id=jNQXAC9IVRw&key={key}")
    if status == 200 and body.get("items"):
        item = body["items"][0]
        print(f"OK   videos.list — '{item['snippet']['title']}' 조회 성공 "
              f"(조회수 {int(item['statistics']['viewCount']):,}, 길이 {item['contentDetails']['duration']})")
    else:
        reason = (body.get("error", {}).get("errors") or [{}])[0].get("reason", "unknown")
        print(f"FAIL videos.list — HTTP {status}, reason: {reason}")
        failures += 1

    # 2) channels.list — 통계 조회 (1유닛)
    status, body = call(f"{base}/channels?part=statistics&id=UC_x5XG1OV2P6uZZ5FSM9Ttw&key={key}")
    if status == 200 and body.get("items"):
        subs = int(body["items"][0]["statistics"].get("subscriberCount", 0))
        print(f"OK   channels.list — 채널 통계 조회 성공 (구독자 {subs:,})")
    else:
        reason = (body.get("error", {}).get("errors") or [{}])[0].get("reason", "unknown")
        print(f"FAIL channels.list — HTTP {status}, reason: {reason}")
        failures += 1

    print(f"\n결과: {'전체 통과 ✅ (2유닛 사용)' if failures == 0 else f'{failures}건 실패 ❌'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

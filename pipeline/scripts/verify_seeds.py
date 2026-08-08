"""시드 채널 RSS 검증 (M1, FR-6).

RSS는 쿼터 0으로 새 영상을 감지하는 1차 경로다. 시드 채널의 피드가 실제로
열리고 최근 영상이 있는지 확인해, 수집이 시작된 뒤에야 문제를 발견하는 상황을 막는다.
쿼터를 전혀 쓰지 않으므로 자유롭게 재실행할 수 있다.

사용:
    python -m scripts.verify_seeds                 # 전체 검증
    python -m scripts.verify_seeds --only food     # 일부만
    python -m scripts.verify_seeds --json out.json # 결과를 파일로
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
import yaml

from app.config import PROJECT_ROOT, ensure_ssl_certificates
from app.rss import RssParseError, channel_feed_url, parse_channel_feed

SEEDS_PATH = PROJECT_ROOT / "config" / "seeds.yaml"
REQUEST_TIMEOUT_S = 15
STALE_AFTER_DAYS = 90  # 이보다 오래 업로드가 없으면 휴면으로 본다


@dataclass
class VerifyResult:
    """채널 하나의 검증 결과."""

    channel_id: str
    title: str
    parent: str
    ok: bool
    entry_count: int = 0
    latest_published: str | None = None
    days_since_upload: int | None = None
    stale: bool = False
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="시드 채널 RSS 검증 (쿼터 0)")
    parser.add_argument("--only", help="쉼표로 구분한 대분류 id")
    parser.add_argument("--json", type=Path, help="결과를 JSON으로 저장할 경로")
    parser.add_argument("--workers", type=int, default=8, help="동시 요청 수 (기본 8)")
    parser.add_argument(
        "--prune",
        action="store_true",
        help=f"RSS 실패·{STALE_AFTER_DAYS}일 초과 휴면 채널을 seeds.yaml에서 제거",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_ssl_certificates()

    if not SEEDS_PATH.exists():
        print(f"시드 파일이 없습니다: {SEEDS_PATH}. 먼저 discover_seeds를 실행하세요.")
        return 1

    data = yaml.safe_load(SEEDS_PATH.read_text(encoding="utf-8")) or {}
    channels_by_parent: dict[str, list[dict[str, Any]]] = data.get("channels", {})

    if args.only:
        wanted = {p.strip() for p in args.only.split(",") if p.strip()}
        channels_by_parent = {k: v for k, v in channels_by_parent.items() if k in wanted}

    targets = [(parent, ch) for parent, chans in channels_by_parent.items() for ch in chans]
    if not targets:
        print("검증할 채널이 없습니다.")
        return 1

    print(f"시드 {len(targets)}개 채널 RSS 검증 (쿼터 0)\n")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda t: _verify(t[0], t[1]), targets))

    _report(results)

    if args.json:
        args.json.write_text(
            json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n결과 저장: {args.json}")

    if args.prune:
        removed = _prune(data, results)
        print(f"\n제거한 채널 {removed}개 · {SEEDS_PATH} 갱신")

    failed = [r for r in results if not r.ok]
    return 1 if failed else 0


def _prune(data: dict[str, Any], results: list[VerifyResult]) -> int:
    """RSS 실패·휴면 채널을 seeds.yaml에서 제거한다.

    Args:
        data: 읽어들인 seeds.yaml 전체.
        results: 검증 결과 목록.

    Returns:
        제거한 채널 수.
    """
    drop_ids = {r.channel_id for r in results if not r.ok or r.stale or r.entry_count == 0}
    if not drop_ids:
        return 0

    removed = 0
    for parent, channels in data.get("channels", {}).items():
        kept = [c for c in channels if str(c.get("id", "")) not in drop_ids]
        removed += len(channels) - len(kept)
        data["channels"][parent] = kept

    header = (
        "# 시드 채널 (SPEC FR-6, D4)\n"
        "#\n"
        "# scripts/discover_seeds.py 가 생성하고 scripts/verify_seeds.py --prune 가 정리한다.\n"
        "# 손으로 추가·삭제해도 된다 — 재실행 시 지정한 대분류만 덮어쓴다.\n"
        "# 국내/해외 태그는 여기 없다 — 영상 소재 단위로 판정하며 (D9),\n"
        "# 채널 카테고리는 M2에서 그 채널 영상들의 분포로 정한다.\n\n"
    )
    SEEDS_PATH.write_text(
        header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return removed


def _verify(parent: str, channel: dict[str, Any]) -> VerifyResult:
    """채널 하나의 RSS를 열어 최근 업로드를 확인한다."""
    channel_id = str(channel.get("id", ""))
    title = str(channel.get("title", ""))
    result = VerifyResult(channel_id=channel_id, title=title, parent=parent, ok=False)

    try:
        response = requests.get(channel_feed_url(channel_id), timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:
        result.error = f"요청 실패: {exc}"
        return result

    if response.status_code != 200:
        result.error = f"HTTP {response.status_code}"
        return result

    try:
        feed = parse_channel_feed(response.text)
    except RssParseError as exc:
        result.error = str(exc)
        return result

    result.ok = True
    result.entry_count = len(feed.entries)

    if feed.entries:
        latest = max(e.published_at for e in feed.entries)
        result.latest_published = latest.isoformat()
        days = (datetime.now(UTC) - latest).days
        result.days_since_upload = days
        result.stale = days > STALE_AFTER_DAYS

    return result


def _report(results: list[VerifyResult]) -> None:
    """검증 결과를 요약해 출력한다."""
    total = len(results)
    passed = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    stale = [r for r in passed if r.stale]
    empty = [r for r in passed if r.entry_count == 0]

    rate = len(passed) / total * 100 if total else 0.0
    print(f"통과 {len(passed)}/{total} ({rate:.1f}%)")

    if failed:
        print(f"\n실패 {len(failed)}개:")
        for r in failed:
            print(f"  [{r.parent}] {r.title[:24]:26} {r.channel_id}  — {r.error}")

    if empty:
        print(f"\n영상 없음 {len(empty)}개:")
        for r in empty:
            print(f"  [{r.parent}] {r.title[:24]:26} {r.channel_id}")

    if stale:
        print(f"\n휴면({STALE_AFTER_DAYS}일 초과) {len(stale)}개:")
        for r in stale:
            print(f"  [{r.parent}] {r.title[:24]:26} 마지막 업로드 {r.days_since_upload}일 전")

    active = [r for r in passed if r.days_since_upload is not None and not r.stale]
    if active:
        median = sorted(r.days_since_upload or 0 for r in active)[len(active) // 2]
        print(f"\n활성 채널 {len(active)}개 · 마지막 업로드 중앙값 {median}일 전")


def _recent_cutoff(days: int) -> datetime:
    """기준 시각을 만든다 (테스트 편의용)."""
    return datetime.now(UTC) - timedelta(days=days)


if __name__ == "__main__":
    sys.exit(main())

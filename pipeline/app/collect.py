"""수집 파이프라인 본체 (FR-6, D8, D10, D12).

한 주기의 흐름:
    1. 추적 채널 RSS 폴링 → 새 영상 감지 (쿼터 0)
    2. 채널 통계 스냅샷 (50개당 1유닛)
    3. 영상 통계 스냅샷 (50개당 1유닛) → 삭제·비공개 영상 제거 (D12)
    4. 분류 → 미분류 표시 (D10)
    5. 30일 purge, 졸업 처리

각 단계는 실패해도 다음 단계를 막지 않는다 — 수집 공백은 다음 주기에 복구된다 (NFR-7).
쿼터는 호출 전에 확인하고, 모자라면 그 단계를 건너뛴다 (NFR-4).
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from app.blocklist import Blocklist
from app.classifier import Classification, KeywordClassifier
from app.quota import QuotaBudget
from app.retention import purge_cutoff, select_channels_to_graduate
from app.rss import RssParseError, channel_feed_url, parse_channel_feed
from app.scoring import is_short_duration
from app.store import Store
from app.thumbnail import safe_thumbnail_url
from app.youtube import COST_LIST, YouTubeApiError, YouTubeClient

RSS_TIMEOUT_S = 15
RSS_WORKERS = 8

# RSS에서 이 기간 안에 올라온 영상만 새로 추적한다 (오래된 영상 역주입 방지).
NEW_VIDEO_MAX_AGE_DAYS = 7


@dataclass
class CollectReport:
    """한 주기 수집 결과.

    Attributes:
        started_at: 시작 시각.
        channels_updated: 스냅샷을 남긴 채널 수.
        videos_updated: 스냅샷을 남긴 영상 수.
        new_videos: RSS로 새로 발견한 영상 수.
        deleted_videos: 삭제·비공개로 제거한 영상 수.
        graduated_channels: 추적을 중단한 채널 수.
        unclassified_rate: 이번 주기 영상의 미분류 비율 (D10).
        quota_used: 사용한 쿼터 유닛.
        errors: 단계별 오류 메시지.
    """

    started_at: datetime
    channels_updated: int = 0
    videos_updated: int = 0
    new_videos: int = 0
    deleted_videos: int = 0
    graduated_channels: int = 0
    unclassified_rate: float = 0.0
    quota_used: int = 0
    errors: list[str] = field(default_factory=list)


def collect_once(
    *,
    store: Store,
    youtube: YouTubeClient,
    classifier: KeywordClassifier,
    blocklist: Blocklist,
    budget: QuotaBudget,
    now: datetime | None = None,
) -> CollectReport:
    """수집 한 주기를 실행한다.

    Args:
        store: Supabase 저장소.
        youtube: API 클라이언트.
        classifier: 키워드 분류기.
        blocklist: 차단 리스트 — 차단 채널은 수집하지 않는다.
        budget: 쿼터 예산.
        now: 기준 시각 (테스트용). 생략하면 현재 UTC.

    Returns:
        수집 결과 요약.
    """
    now = now or datetime.now(UTC)
    report = CollectReport(started_at=now)
    run_id = _safe(report, "실행 기록 시작", lambda: store.start_run(now))

    channels = _safe(report, "추적 채널 조회", store.tracked_channels) or []
    channels = [c for c in channels if not blocklist.is_channel_blocked(str(c.get("channel_id", "")))]
    if not channels:
        report.errors.append("추적 채널이 없습니다 — 시드를 먼저 등재하세요.")
        _finish(store, run_id, report, youtube, now)
        return report

    channel_ids = [str(c["channel_id"]) for c in channels]

    # 1. RSS로 새 영상 감지 (쿼터 0)
    feeds = _poll_feeds(channel_ids, report)
    new_video_ids = _new_video_ids(feeds, now)
    report.new_videos = len(new_video_ids)

    # 2. 채널 통계 스냅샷
    report.channels_updated = _snapshot_channels(store, youtube, budget, channel_ids, now, report)

    # 3. 영상 통계 스냅샷 (RSS 신규 + DB의 최근 영상)
    tracked_video_ids = _safe(
        report, "추적 영상 조회", lambda: store.recent_video_ids(now - timedelta(days=NEW_VIDEO_MAX_AGE_DAYS))
    ) or []
    target_video_ids = sorted(set(new_video_ids) | set(tracked_video_ids))
    report.videos_updated, report.deleted_videos, report.unclassified_rate = _snapshot_videos(
        store, youtube, budget, classifier, blocklist, target_video_ids, now, report
    )

    # 4. 보관 정책 · 졸업
    _safe(report, "보관 정책 purge", lambda: store.purge_before(purge_cutoff(now)))
    graduating = select_channels_to_graduate(
        [{**c, "last_upload_at": _parse_dt(c.get("last_upload_at"))} for c in channels], now=now
    )
    if graduating:
        ids = [str(c["channel_id"]) for c in graduating]
        report.graduated_channels = (
            _safe(report, "채널 졸업 처리", lambda: store.graduate_channels(ids, at=now)) or 0
        )

    _finish(store, run_id, report, youtube, now)
    return report


def _poll_feeds(channel_ids: Sequence[str], report: CollectReport) -> list[Any]:
    """추적 채널의 RSS를 병렬로 읽는다 (쿼터 0)."""

    def fetch(channel_id: str) -> Any:
        try:
            response = requests.get(channel_feed_url(channel_id), timeout=RSS_TIMEOUT_S)
            if response.status_code != 200:
                return None
            return parse_channel_feed(response.text)
        except (requests.RequestException, RssParseError):
            return None

    with ThreadPoolExecutor(max_workers=RSS_WORKERS) as pool:
        feeds = list(pool.map(fetch, channel_ids))

    failed = sum(1 for f in feeds if f is None)
    if failed:
        report.errors.append(f"RSS 실패 {failed}/{len(channel_ids)}개 채널")
    return [f for f in feeds if f is not None]


def _new_video_ids(feeds: Sequence[Any], now: datetime) -> list[str]:
    """피드에서 최근 업로드 영상 id를 모은다."""
    cutoff = now - timedelta(days=NEW_VIDEO_MAX_AGE_DAYS)
    return [e.video_id for feed in feeds for e in feed.entries if e.published_at >= cutoff]


def _snapshot_channels(
    store: Store,
    youtube: YouTubeClient,
    budget: QuotaBudget,
    channel_ids: Sequence[str],
    now: datetime,
    report: CollectReport,
) -> int:
    """채널 통계를 읽어 스냅샷으로 남긴다."""
    cost = _batch_cost(len(channel_ids))
    if not budget.can_afford(cost):
        report.errors.append(f"쿼터 부족으로 채널 스냅샷 건너뜀 (필요 {cost}, 남음 {budget.remaining})")
        return 0

    try:
        details = youtube.fetch_channels(list(channel_ids))
    except YouTubeApiError as exc:
        report.errors.append(f"채널 통계 조회 실패: {exc}")
        return 0
    budget.spend(cost)

    snapshots = [
        {
            "channel_id": c["channel_id"],
            "captured_at": now.isoformat(),
            "subscriber_count": c["subscriber_count"],
            "view_count": c["view_count"],
            "video_count": c["video_count"],
        }
        for c in details
    ]
    metas = [
        {
            "channel_id": c["channel_id"],
            "title": c["title"],
            # 브라우저의 img src로 들어가므로 호스트를 검증해 저장한다.
            "thumbnail_url": safe_thumbnail_url(c["thumbnail_url"]),
        }
        for c in details
    ]
    _safe(report, "채널 메타 갱신", lambda: store.upsert_channels(metas))
    return _safe(report, "채널 스냅샷 적재", lambda: store.insert_channel_snapshots(snapshots)) or 0


def _snapshot_videos(
    store: Store,
    youtube: YouTubeClient,
    budget: QuotaBudget,
    classifier: KeywordClassifier,
    blocklist: Blocklist,
    video_ids: Sequence[str],
    now: datetime,
    report: CollectReport,
) -> tuple[int, int, float]:
    """영상 통계를 읽어 스냅샷으로 남기고, 사라진 영상을 제거한다."""
    if not video_ids:
        return 0, 0, 0.0

    cost = _batch_cost(len(video_ids))
    if not budget.can_afford(cost):
        report.errors.append(f"쿼터 부족으로 영상 스냅샷 건너뜀 (필요 {cost}, 남음 {budget.remaining})")
        return 0, 0, 0.0

    try:
        details = youtube.fetch_videos(list(video_ids))
    except YouTubeApiError as exc:
        report.errors.append(f"영상 통계 조회 실패: {exc}")
        return 0, 0, 0.0
    budget.spend(cost)

    # 응답에 없는 영상은 삭제·비공개된 것이다 (D12).
    returned = {v["video_id"] for v in details}
    missing = [vid for vid in video_ids if vid not in returned]
    deleted = _safe(report, "삭제 영상 제거", lambda: store.delete_videos(missing)) or 0

    kept = [v for v in details if not blocklist.is_video_blocked(v["video_id"])]
    classifications: list[Classification] = []
    metas: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []

    for video in kept:
        result = classifier.classify(
            video["title"], tags=video.get("tags"), description=video.get("description", "")
        )
        classifications.append(result)
        metas.append(
            {
                "video_id": video["video_id"],
                "channel_id": video["channel_id"],
                "title": video["title"],
                "thumbnail_url": safe_thumbnail_url(video["thumbnail_url"]),
                "published_at": video["published_at"],
                "duration_s": video["duration_s"],
                "is_short": is_short_duration(video["duration_s"]),
                "age_restricted": video["age_restricted"],
                "category_ids": [result.category_id] if result.category_id else [],
                "unclassified": result.unclassified,
            }
        )
        snapshots.append(
            {
                "video_id": video["video_id"],
                "captured_at": now.isoformat(),
                "view_count": video["view_count"],
            }
        )

    _safe(report, "영상 메타 갱신", lambda: store.upsert_videos(metas))
    updated = _safe(report, "영상 스냅샷 적재", lambda: store.insert_video_snapshots(snapshots)) or 0
    return updated, deleted, KeywordClassifier.unclassified_rate(classifications)


def _batch_cost(item_count: int) -> int:
    """50개당 1유닛인 배치 호출의 쿼터 비용."""
    return ((item_count + 49) // 50) * COST_LIST


def _parse_dt(value: Any) -> datetime | None:
    """ISO 문자열을 datetime으로 바꾼다 (실패하면 None)."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe(report: CollectReport, label: str, action: Any) -> Any:
    """한 단계가 실패해도 나머지를 진행한다 (NFR-7)."""
    try:
        return action()
    except Exception as exc:  # noqa: BLE001 - 어떤 실패든 다음 단계를 막지 않는다
        report.errors.append(f"{label} 실패: {exc}")
        return None


def _finish(
    store: Store, run_id: int | None, report: CollectReport, youtube: YouTubeClient, now: datetime
) -> None:
    """실행 기록을 마감한다."""
    report.quota_used = youtube.quota_used
    _safe(
        report,
        "실행 기록 마감",
        lambda: store.finish_run(
            run_id,
            at=datetime.now(UTC),
            quota_used=report.quota_used,
            videos_updated=report.videos_updated,
            channels_updated=report.channels_updated,
            errors=report.errors,
        ),
    )

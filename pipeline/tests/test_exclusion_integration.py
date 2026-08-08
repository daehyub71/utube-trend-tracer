"""제외 규칙 통합 테스트 (FR-10, D10, D12).

차단·연령제한·미분류는 서로 다른 이유로 랭킹에서 빠진다. 각각은 단위 테스트가
있지만, 실제로는 산출 경로 끝에서 함께 걸러진다 — 한 군데라도 새면 부적절한
콘텐츠가 노출된다. 이 테스트는 그 합류 지점을 지킨다.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.blocklist import Blocklist, load_blocklist
from app.ranking import VideoSeries, rank_rising_videos, rank_trending_videos
from app.scoring import Snapshot

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)

BLOCKLIST_YAML = """
version: 1
channels:
  - id: UC_banned
    reason: 소유자 opt-out 요청
videos:
  - id: vid_banned
    reason: 낚시성 제목
"""


@pytest.fixture
def blocklist(tmp_path: Path) -> Blocklist:
    path = tmp_path / "blocklist.yaml"
    path.write_text(BLOCKLIST_YAML, encoding="utf-8")
    return load_blocklist(path)


def series(video_id: str, *, channel_id: str = "UC_ok") -> VideoSeries:
    return VideoSeries(
        video_id=video_id,
        channel_id=channel_id,
        category_id="food_domestic",
        subscribers=10_000,
        is_short=False,
        published_at=NOW - timedelta(days=1),
        snapshots=[
            Snapshot(captured_at=NOW - timedelta(hours=24), value=0),
            Snapshot(captured_at=NOW, value=50_000),
        ],
    )


def candidates() -> list[dict[str, object]]:
    """수집 직후의 랭킹 후보 — 각기 다른 이유로 빠져야 할 항목이 섞여 있다."""
    ok = {"age_restricted": False, "unclassified": False}
    return [
        {"video_id": "clean", "channel_id": "UC_ok", **ok},
        {"video_id": "vid_banned", "channel_id": "UC_ok", **ok},
        {"video_id": "from_banned", "channel_id": "UC_banned", **ok},
        {"video_id": "adult", "channel_id": "UC_ok", "age_restricted": True, "unclassified": False},
        {"video_id": "unknown", "channel_id": "UC_ok", "age_restricted": False, "unclassified": True},
    ]


def test_all_four_exclusion_reasons_apply_together(blocklist: Blocklist) -> None:
    """차단 영상·차단 채널·연령제한·미분류가 한 번에 걸러진다."""
    kept = blocklist.filter_videos(candidates())

    assert [v["video_id"] for v in kept] == ["clean"]


def test_blocked_video_never_reaches_any_board(blocklist: Blocklist) -> None:
    """필터를 통과한 항목만 산출에 들어가므로, 차단 영상은 두 보드 어디에도 없다."""
    kept_ids = {str(v["video_id"]) for v in blocklist.filter_videos(candidates())}
    ranked = [series(vid) for vid in kept_ids]

    trending = rank_trending_videos(ranked, now=NOW)
    rising = rank_rising_videos(ranked, now=NOW)

    for entries in (trending, rising):
        ids = {e.entity_id for e in entries}
        assert "vid_banned" not in ids
        assert "from_banned" not in ids
        assert "adult" not in ids
        assert "unknown" not in ids


def test_clean_video_still_ranks(blocklist: Blocklist) -> None:
    """제외 규칙이 정상 항목까지 지우면 안 된다."""
    kept_ids = {str(v["video_id"]) for v in blocklist.filter_videos(candidates())}
    ranked = rank_trending_videos([series(vid) for vid in kept_ids], now=NOW)

    assert [e.entity_id for e in ranked] == ["clean"]


def test_opt_out_takes_effect_without_code_change(tmp_path: Path) -> None:
    """opt-out 요청은 설정 파일만 고쳐 반영된다 (FR-10, D12).

    운영자가 코드를 배포하지 않고 차단할 수 있어야 요청에 빠르게 응할 수 있다.
    """
    path = tmp_path / "blocklist.yaml"
    path.write_text("version: 1\nchannels: []\nvideos: []\n", encoding="utf-8")
    before = load_blocklist(path)
    assert before.is_channel_blocked("UC_request") is False

    path.write_text(
        "version: 1\nchannels:\n  - id: UC_request\n    reason: 소유자 요청\nvideos: []\n",
        encoding="utf-8",
    )
    after = load_blocklist(path)

    assert after.is_channel_blocked("UC_request") is True
    assert after.channel_reason("UC_request") == "소유자 요청"

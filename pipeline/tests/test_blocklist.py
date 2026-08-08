"""차단 리스트 테스트 (FR-10, D12).

차단·연령제한 항목이 랭킹에 새어 나가지 않아야 한다.
차단은 "확실할 때만 통과"가 아니라 "걸리면 무조건 제외"가 규약이다.
"""

from pathlib import Path

import pytest

from app.blocklist import Blocklist, BlocklistError, load_blocklist

SAMPLE = """
version: 1
channels:
  - id: UC_blocked_channel
    reason: 소유자 opt-out 요청
videos:
  - id: vid_blocked
    reason: 낚시성 제목
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "blocklist.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def blocklist(tmp_path: Path) -> Blocklist:
    return load_blocklist(write(tmp_path, SAMPLE))


def test_blocks_listed_channel(blocklist: Blocklist) -> None:
    assert blocklist.is_channel_blocked("UC_blocked_channel") is True
    assert blocklist.is_channel_blocked("UC_normal_channel") is False


def test_blocks_listed_video(blocklist: Blocklist) -> None:
    assert blocklist.is_video_blocked("vid_blocked") is True
    assert blocklist.is_video_blocked("vid_normal") is False


def test_keeps_reason_for_audit(blocklist: Blocklist) -> None:
    """등재 사유를 보관한다 — 해제 판단·admin 리포트 근거."""
    assert blocklist.channel_reason("UC_blocked_channel") == "소유자 opt-out 요청"


def test_empty_blocklist_blocks_nothing(tmp_path: Path) -> None:
    """비어 있는 리스트는 아무것도 막지 않는다 (초기 상태)."""
    empty = load_blocklist(write(tmp_path, "version: 1\nchannels: []\nvideos: []\n"))

    assert empty.is_channel_blocked("UC_any") is False
    assert empty.is_video_blocked("any") is False


def test_load_real_config_file() -> None:
    """리포에 커밋된 실제 config/blocklist.yaml이 유효해야 한다."""
    assert isinstance(load_blocklist(), Blocklist)


def test_missing_file_raises(tmp_path: Path) -> None:
    """파일이 없으면 조용히 '차단 없음'으로 넘어가지 않는다 (안전장치 무력화 방지)."""
    with pytest.raises(BlocklistError):
        load_blocklist(tmp_path / "nope.yaml")


def test_entry_without_id_raises(tmp_path: Path) -> None:
    """id 없는 항목은 실패시킨다 — 조용히 무시하면 차단이 안 걸린 걸 모른다."""
    with pytest.raises(BlocklistError, match="id"):
        load_blocklist(write(tmp_path, "version: 1\nchannels:\n  - reason: 사유만 있음\nvideos: []\n"))


def test_filter_videos_excludes_blocked_and_restricted(blocklist: Blocklist) -> None:
    """랭킹 후보에서 차단·연령제한·미분류를 한 번에 걸러낸다 (FR-10, D10, D12)."""
    ok = {"age_restricted": False, "unclassified": False}
    candidates = [
        {"video_id": "ok", "channel_id": "UC_ok", **ok},
        {"video_id": "vid_blocked", "channel_id": "UC_ok", **ok},
        {"video_id": "v2", "channel_id": "UC_blocked_channel", **ok},
        {"video_id": "v3", "channel_id": "UC_ok", "age_restricted": True, "unclassified": False},
        {"video_id": "v4", "channel_id": "UC_ok", "age_restricted": False, "unclassified": True},
    ]

    kept = blocklist.filter_videos(candidates)

    assert [v["video_id"] for v in kept] == ["ok"]


def test_filter_videos_blocks_by_owning_channel(blocklist: Blocklist) -> None:
    """차단된 채널의 영상은 영상 id가 깨끗해도 제외된다."""
    kept = blocklist.filter_videos(
        [
            {
                "video_id": "clean",
                "channel_id": "UC_blocked_channel",
                "age_restricted": False,
                "unclassified": False,
            }
        ]
    )

    assert kept == []

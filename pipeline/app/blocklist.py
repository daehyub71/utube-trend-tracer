"""수동 차단 리스트 (FR-10, D12).

차단된 채널·영상, 연령제한 영상, 미분류 항목을 랭킹 후보에서 제외한다.
차단이 조용히 무력화되면 안 되므로, 파일 누락·형식 오류는 예외로 즉시 드러낸다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import yaml

from app.config import PROJECT_ROOT

DEFAULT_BLOCKLIST_PATH = PROJECT_ROOT / "config" / "blocklist.yaml"


class BlocklistError(RuntimeError):
    """차단 리스트가 없거나 형식이 잘못된 경우."""


class Blocklist:
    """차단 대상 채널·영상 판정기."""

    def __init__(self, channels: dict[str, str], videos: dict[str, str]) -> None:
        """차단 리스트를 만든다.

        Args:
            channels: 채널 id → 등재 사유.
            videos: 영상 id → 등재 사유.
        """
        self._channels = channels
        self._videos = videos

    def is_channel_blocked(self, channel_id: str) -> bool:
        """채널이 차단 대상인지 확인한다."""
        return channel_id in self._channels

    def is_video_blocked(self, video_id: str) -> bool:
        """영상이 차단 대상인지 확인한다."""
        return video_id in self._videos

    def channel_reason(self, channel_id: str) -> str | None:
        """채널의 등재 사유를 돌려준다."""
        return self._channels.get(channel_id)

    def video_reason(self, video_id: str) -> str | None:
        """영상의 등재 사유를 돌려준다."""
        return self._videos.get(video_id)

    def filter_videos(self, videos: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """랭킹 후보에서 제외 대상을 걸러낸다.

        제외 조건: 차단된 영상, 차단된 채널의 영상 (FR-10),
        연령제한 영상 (D12), 미분류 항목 (D10).

        Args:
            videos: `video_id`, `channel_id`, `age_restricted`, `unclassified` 키를 가진 dict 목록.

        Returns:
            남은 영상 목록.
        """
        return [
            v
            for v in videos
            if not self.is_video_blocked(str(v.get("video_id", "")))
            and not self.is_channel_blocked(str(v.get("channel_id", "")))
            and not v.get("age_restricted", False)
            and not v.get("unclassified", False)
        ]

    def filter_channels(self, channels: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """랭킹 후보 채널에서 차단·미분류를 걸러낸다."""
        return [
            c
            for c in channels
            if not self.is_channel_blocked(str(c.get("channel_id", "")))
            and not c.get("unclassified", False)
        ]


def load_blocklist(path: Path | None = None) -> Blocklist:
    """차단 리스트를 읽는다.

    Args:
        path: blocklist.yaml 경로. 생략하면 `config/blocklist.yaml`.

    Returns:
        Blocklist 인스턴스.

    Raises:
        BlocklistError: 파일이 없거나 항목에 id가 빠진 경우.
    """
    config_path = path or DEFAULT_BLOCKLIST_PATH
    if not config_path.exists():
        raise BlocklistError(f"차단 리스트 파일이 없습니다: {config_path}")

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise BlocklistError(f"{config_path}: YAML 파싱 실패 — {exc}") from exc

    if not isinstance(data, dict):
        raise BlocklistError(f"{config_path}: 최상위가 매핑이 아닙니다.")

    return Blocklist(
        channels=_entries(data.get("channels"), "channels", config_path),
        videos=_entries(data.get("videos"), "videos", config_path),
    )


def _entries(raw: Any, section: str, path: Path) -> dict[str, str]:
    """차단 항목 목록을 id → 사유 매핑으로 바꾼다."""
    if raw is None:
        return {}
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        raise BlocklistError(f"{path}: {section} 는 목록이어야 합니다.")

    entries: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise BlocklistError(f"{path}: {section} 항목은 매핑이어야 합니다.")
        entry_id = str(item.get("id") or "").strip()
        if not entry_id:
            raise BlocklistError(f"{path}: {section} 항목에 id가 없습니다 — {item!r}")
        entries[entry_id] = str(item.get("reason") or "")
    return entries

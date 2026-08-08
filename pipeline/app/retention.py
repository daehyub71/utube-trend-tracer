"""보관 정책과 채널 졸업 (NFR-1, D11, D12).

30일 롤링은 무료 용량 관리이기 이전에 YouTube 약관 요구사항이다.
졸업은 발굴로 늘어나는 추적 채널이 상한을 넘지 않게 하는 유일한 장치다 —
없으면 쿼터와 DB가 함께 압박받는다.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

# 30일 롤링 (NFR-1)
RETENTION_DAYS = 30

# 추적 채널 상한 (D11)
TRACKED_CHANNEL_LIMIT = 2_000

# 이 기간 업로드가 없으면 졸업 후보 (D11)
DORMANT_DAYS = 30


def purge_cutoff(now: datetime) -> datetime:
    """이 시각보다 오래된 스냅샷·영상은 삭제 대상이다."""
    return now - timedelta(days=RETENTION_DAYS)


def graduation_candidates(channels: Sequence[dict[str, Any]], *, now: datetime) -> list[dict[str, Any]]:
    """휴면 채널을 골라낸다 (D11).

    수동 시드는 운영자가 고른 채널이므로 자동 졸업 대상에서 뺀다.

    Args:
        channels: `channel_id`, `last_upload_at`, `is_seed` 를 가진 dict 목록.
        now: 기준 시각.

    Returns:
        졸업 후보 목록.
    """
    dormant_before = now - timedelta(days=DORMANT_DAYS)
    candidates: list[dict[str, Any]] = []
    for channel in channels:
        if channel.get("is_seed"):
            continue
        last_upload = channel.get("last_upload_at")
        if last_upload is None or (isinstance(last_upload, datetime) and last_upload < dormant_before):
            candidates.append(channel)
    return candidates


def select_channels_to_graduate(
    channels: Sequence[dict[str, Any]],
    *,
    now: datetime,
    limit: int = TRACKED_CHANNEL_LIMIT,
) -> list[dict[str, Any]]:
    """추적을 중단할 채널을 정한다 (D11).

    먼저 휴면 채널을 정리하고, 그래도 상한을 넘으면 성과 하위부터 추가로 졸업시킨다.
    시드 채널은 상한 압박에서도 남긴다.

    Args:
        channels: 현재 추적 중인 채널 목록.
        now: 기준 시각.
        limit: 추적 채널 상한.

    Returns:
        졸업시킬 채널 목록.
    """
    dormant = graduation_candidates(channels, now=now)
    dormant_ids = {c["channel_id"] for c in dormant}

    survivors = [c for c in channels if c["channel_id"] not in dormant_ids]
    if len(survivors) <= limit:
        return list(dormant)

    # 상한 초과분을 성과 하위부터 채운다 (시드 제외).
    prunable = sorted(
        (c for c in survivors if not c.get("is_seed")),
        key=lambda c: float(c.get("recent_score") or 0.0),
    )
    overflow = len(survivors) - limit
    return list(dormant) + prunable[:overflow]

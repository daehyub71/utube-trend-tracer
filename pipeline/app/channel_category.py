"""채널 카테고리 확정 (D9 이월 과제, SPEC FR-1).

채널 제목·설명만으로 국내/해외를 판정하면 오탐이 잦다 (다국어 설명을 쓰는
한국 채널이 해외로 분류됨). 그래서 **채널의 카테고리는 그 채널 영상들의
소재 분포로 정한다** — 시드 등재 시점에는 대분류만 두고, 영상이 쌓인 뒤 확정한다.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

# 이 개수 미만이면 분포를 신뢰하지 않는다 (영상 1~2개로 채널 성격을 정하지 않는다).
MIN_VIDEOS_FOR_TAG = 3


def resolve_channel_category(
    video_category_ids: Sequence[str], *, fallback_parent: str | None = None
) -> str | None:
    """영상들의 카테고리 분포로 채널 카테고리를 정한다.

    Args:
        video_category_ids: 그 채널 영상들의 카테고리 id 목록 (미분류는 제외하고 넘긴다).
        fallback_parent: 근거가 모자랄 때 쓸 대분류 id (시드 등재 시 기록한 값).

    Returns:
        `{parent}_{tag}` 형식의 카테고리 id. 정할 수 없으면 None.

    분포가 MIN_VIDEOS_FOR_TAG 미만이면 대분류만 아는 것이므로,
    fallback_parent 에 기본 태그(domestic)를 붙여 돌려준다.
    """
    classified = [c for c in video_category_ids if c]

    if len(classified) >= MIN_VIDEOS_FOR_TAG:
        return Counter(classified).most_common(1)[0][0]

    # 근거가 모자라면 대분류 + 기본 태그로 둔다 (D9: 기본값은 국내).
    if classified:
        return Counter(classified).most_common(1)[0][0]
    if fallback_parent:
        return f"{fallback_parent}_domestic"
    return None


def dominant_parent(video_category_ids: Sequence[str]) -> str | None:
    """영상 분포에서 가장 잦은 대분류를 고른다 (태그 무시)."""
    parents = [c.rsplit("_", 1)[0] for c in video_category_ids if c and "_" in c]
    if not parents:
        return None
    return Counter(parents).most_common(1)[0][0]

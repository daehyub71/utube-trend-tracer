"""썸네일 URL 검증 (보안 리뷰 2026-08-08).

썸네일은 브라우저의 `<img src>` 로 그대로 들어간다. 지금은 값의 출처가 YouTube API뿐이라
악용 경로가 없지만, DB 쓰기가 뚫린 상황에서 임의 호스트가 들어가면 방문자 IP·Referer가
그 호스트로 새어나간다. 저장 시점에 호스트를 좁혀 그 경로를 없앤다.
"""

from __future__ import annotations

from urllib.parse import urlparse

# YouTube가 썸네일·아바타를 서빙하는 호스트
ALLOWED_HOST_SUFFIXES = (
    ".ytimg.com",
    ".ggpht.com",
    ".googleusercontent.com",
)


def safe_thumbnail_url(url: str | None) -> str | None:
    """허용된 호스트의 https URL만 통과시킨다.

    Args:
        url: YouTube API가 준 썸네일 주소.

    Returns:
        검증을 통과한 URL, 아니면 None (호출자는 대체 표시를 쓴다).
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    if parsed.scheme != "https":
        return None

    # urlparse 는 `user@host` 를 hostname 으로 분리해 주므로 위장 호스트가 걸러진다.
    host = (parsed.hostname or "").lower()
    if not host:
        return None

    return url if host.endswith(ALLOWED_HOST_SUFFIXES) else None

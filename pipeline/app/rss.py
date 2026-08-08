"""채널 RSS 피드 파싱 (FR-6).

RSS는 쿼터를 쓰지 않고 새 영상을 감지하는 1차 경로다.
응답이 깨졌을 때 '영상 0개'로 조용히 넘어가면 수집 중단을 알아채지 못하므로,
형식 오류는 RssParseError로 드러낸다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree

FEED_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

_ATOM = "{http://www.w3.org/2005/Atom}"
_YT = "{http://www.youtube.com/xml/schemas/2015}"
_MEDIA = "{http://search.yahoo.com/mrss/}"


class RssParseError(RuntimeError):
    """RSS 응답이 깨졌거나 피드 형식이 아닌 경우."""


@dataclass(frozen=True)
class FeedEntry:
    """피드의 영상 항목 하나.

    Attributes:
        video_id: 영상 id.
        channel_id: 채널 id.
        title: 제목 — 분류 입력.
        published_at: 업로드 시각 (tz 포함).
        description: 설명 — 분류 입력.
    """

    video_id: str
    channel_id: str
    title: str
    published_at: datetime
    description: str = ""


@dataclass(frozen=True)
class ChannelFeed:
    """채널 하나의 피드.

    Attributes:
        channel_id: 채널 id.
        title: 채널명.
        entries: 최신순 영상 목록 (YouTube가 주는 순서 그대로).
    """

    channel_id: str
    title: str
    entries: list[FeedEntry]


def channel_feed_url(channel_id: str) -> str:
    """채널 id로 RSS 주소를 만든다."""
    return FEED_URL_TEMPLATE.format(channel_id=channel_id)


def parse_channel_feed(xml_text: str) -> ChannelFeed:
    """RSS XML을 파싱한다.

    Args:
        xml_text: 피드 응답 본문.

    Returns:
        채널 메타와 영상 목록.

    Raises:
        RssParseError: XML이 깨졌거나 Atom 피드가 아닌 경우.
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise RssParseError(f"RSS XML 파싱 실패 — {exc}") from exc

    if root.tag != f"{_ATOM}feed":
        raise RssParseError(f"Atom 피드가 아닙니다 (최상위 태그: {root.tag}).")

    channel_id = _text(root.find(f"{_YT}channelId"))
    if not channel_id:
        raise RssParseError("피드에 channelId가 없습니다.")

    entries: list[FeedEntry] = []
    for node in root.findall(f"{_ATOM}entry"):
        video_id = _text(node.find(f"{_YT}videoId"))
        published_raw = _text(node.find(f"{_ATOM}published"))
        if not video_id or not published_raw:
            # 항목 하나가 불완전해도 나머지는 살린다 (NFR-7).
            continue
        try:
            published_at = datetime.fromisoformat(published_raw)
        except ValueError:
            continue
        entries.append(
            FeedEntry(
                video_id=video_id,
                channel_id=_text(node.find(f"{_YT}channelId")) or channel_id,
                title=_text(node.find(f"{_ATOM}title")),
                published_at=published_at,
                description=_text(node.find(f"{_MEDIA}group/{_MEDIA}description")),
            )
        )

    return ChannelFeed(
        channel_id=channel_id,
        title=_text(root.find(f"{_ATOM}title")),
        entries=entries,
    )


def _text(node: ElementTree.Element | None) -> str:
    """엘리먼트의 텍스트를 안전하게 꺼낸다."""
    if node is None or node.text is None:
        return ""
    return node.text.strip()

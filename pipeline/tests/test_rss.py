"""채널 RSS 피드 파싱 테스트 (FR-6).

RSS는 쿼터 0으로 새 영상을 감지하는 수단이라 수집기의 1차 경로다.
네트워크 없이 검증하기 위해 실제 응답 형태의 XML 픽스처를 쓴다.
"""

import pytest

from app.rss import RssParseError, channel_feed_url, parse_channel_feed

FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <yt:channelId>UCtest123</yt:channelId>
  <title>테스트 채널</title>
  <entry>
    <yt:videoId>vid_a</yt:videoId>
    <yt:channelId>UCtest123</yt:channelId>
    <title>첫 번째 영상 제목</title>
    <published>2026-08-07T09:00:00+00:00</published>
    <media:group>
      <media:description>영상 설명입니다</media:description>
    </media:group>
  </entry>
  <entry>
    <yt:videoId>vid_b</yt:videoId>
    <yt:channelId>UCtest123</yt:channelId>
    <title>두 번째 영상</title>
    <published>2026-08-06T12:30:00+00:00</published>
    <media:group>
      <media:description></media:description>
    </media:group>
  </entry>
</feed>
"""


def test_feed_url_is_built_from_channel_id() -> None:
    """채널 id로 RSS 주소를 만든다 (쿼터 0 경로)."""
    assert channel_feed_url("UCtest123") == (
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest123"
    )


def test_parse_returns_channel_metadata() -> None:
    feed = parse_channel_feed(FEED_XML)

    assert feed.channel_id == "UCtest123"
    assert feed.title == "테스트 채널"


def test_parse_returns_entries_in_order() -> None:
    feed = parse_channel_feed(FEED_XML)

    assert [e.video_id for e in feed.entries] == ["vid_a", "vid_b"]
    assert feed.entries[0].title == "첫 번째 영상 제목"


def test_parse_reads_published_as_datetime() -> None:
    """업로드 시각은 datetime으로 — Δ시간 실측의 기준이 된다 (FR-7)."""
    entry = parse_channel_feed(FEED_XML).entries[0]

    assert entry.published_at.year == 2026
    assert entry.published_at.month == 8
    assert entry.published_at.day == 7
    assert entry.published_at.tzinfo is not None


def test_parse_reads_description() -> None:
    """설명은 분류 입력으로 쓰인다 (FR-1)."""
    entries = parse_channel_feed(FEED_XML).entries

    assert entries[0].description == "영상 설명입니다"
    assert entries[1].description == ""


def test_parse_empty_feed_has_no_entries() -> None:
    """영상이 없는 채널도 유효한 피드다 (신규 채널)."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <yt:channelId>UCempty</yt:channelId>
  <title>빈 채널</title>
</feed>
"""
    feed = parse_channel_feed(xml)

    assert feed.channel_id == "UCempty"
    assert feed.entries == []


def test_parse_rejects_malformed_xml() -> None:
    """깨진 응답은 조용히 '영상 0개'로 넘기지 않는다 — 검증 실패로 드러낸다."""
    with pytest.raises(RssParseError):
        parse_channel_feed("<not-xml")


def test_parse_rejects_non_feed_document() -> None:
    """RSS가 아닌 문서(404 HTML 등)도 실패로 처리한다."""
    with pytest.raises(RssParseError):
        parse_channel_feed("<html><body>Not Found</body></html>")

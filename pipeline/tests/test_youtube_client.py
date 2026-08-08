"""YouTube 클라이언트 테스트 (FR-6, D8, D12).

네트워크 없이 응답 파싱과 쿼터 누적을 검증한다.
`duration_s` 는 Shorts 판별의 입력이므로 정확해야 한다 (D8).
"""

from typing import Any

import pytest

from app.youtube import COST_LIST, COST_SEARCH, YouTubeApiError, YouTubeClient, parse_duration


class TestParseDuration:
    @pytest.mark.parametrize(
        ("iso", "seconds"),
        [
            ("PT19S", 19),
            ("PT1M", 60),
            ("PT3M", 180),
            ("PT3M1S", 181),
            ("PT1H", 3600),
            ("PT1H2M3S", 3723),
            ("P1DT2H", 93_600),
        ],
    )
    def test_parses_iso8601_duration(self, iso: str, seconds: int) -> None:
        assert parse_duration(iso) == seconds

    def test_unknown_duration_is_none(self) -> None:
        """길이를 못 받으면 None — Shorts 보정을 함부로 걸지 않기 위해서다."""
        assert parse_duration("") is None
        assert parse_duration("garbage") is None

    def test_live_stream_zero_duration_is_none(self) -> None:
        """진행 중 라이브는 PT0S로 온다 — 길이 미상으로 취급한다."""
        assert parse_duration("PT0S") is None


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


class TestFetchVideos:
    def test_parses_fields_needed_for_scoring(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {
            "items": [
                {
                    "id": "vid1",
                    "snippet": {
                        "channelId": "UC1",
                        "title": "제목",
                        "description": "설명",
                        "tags": ["먹방"],
                        "publishedAt": "2026-08-07T09:00:00Z",
                        "thumbnails": {"medium": {"url": "https://img/1.jpg"}},
                    },
                    "statistics": {"viewCount": "12345", "likeCount": "678"},
                    "contentDetails": {"duration": "PT2M30S"},
                }
            ]
        }
        client = _client_returning(monkeypatch, payload)

        videos = client.fetch_videos(["vid1"])

        assert videos[0]["video_id"] == "vid1"
        assert videos[0]["view_count"] == 12_345
        assert videos[0]["duration_s"] == 150
        assert videos[0]["age_restricted"] is False
        assert videos[0]["tags"] == ["먹방"]

    def test_flags_age_restricted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """연령제한 영상은 랭킹에서 제외해야 하므로 표시한다 (D12)."""
        payload = {
            "items": [
                {
                    "id": "vid1",
                    "snippet": {"channelId": "UC1", "title": "t", "publishedAt": "2026-08-07T09:00:00Z"},
                    "statistics": {"viewCount": "1"},
                    "contentDetails": {
                        "duration": "PT5M",
                        "contentRating": {"ytRating": "ytAgeRestricted"},
                    },
                }
            ]
        }
        client = _client_returning(monkeypatch, payload)

        assert client.fetch_videos(["vid1"])[0]["age_restricted"] is True

    def test_missing_videos_are_omitted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """삭제·비공개 영상은 응답에서 빠진다 — 호출자가 DB에서 지운다 (D12)."""
        client = _client_returning(monkeypatch, {"items": []})

        assert client.fetch_videos(["gone"]) == []

    def test_batches_fifty_at_a_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """50개당 1유닛 — 배치 크기가 쿼터 효율을 좌우한다."""
        calls: list[dict[str, Any]] = []

        def fake_get(url: str, params: dict[str, Any], timeout: int) -> FakeResponse:
            calls.append(params)
            return FakeResponse({"items": []})

        monkeypatch.setattr("app.youtube.requests.get", fake_get)
        client = YouTubeClient(api_key="k")

        client.fetch_videos([f"v{i}" for i in range(120)])

        assert len(calls) == 3  # 50 + 50 + 20
        assert client.quota_used == 3 * COST_LIST


class TestQuotaAccounting:
    def test_search_costs_one_hundred(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """search.list는 100유닛 — 예산제로만 부른다 (D14)."""
        client = _client_returning(monkeypatch, {"items": []})

        client.search_channels("먹방")

        assert client.quota_used == COST_SEARCH

    def test_quota_counted_even_on_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """오류 응답도 쿼터를 쓴다 — 실패했다고 공짜가 아니다."""
        client = _client_returning(monkeypatch, {"error": {"errors": [{"reason": "quotaExceeded"}]}}, 403)

        with pytest.raises(YouTubeApiError):
            client.fetch_videos(["v1"])

        assert client.quota_used == COST_LIST


def _client_returning(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], status: int = 200
) -> YouTubeClient:
    monkeypatch.setattr(
        "app.youtube.requests.get",
        lambda url, params, timeout: FakeResponse(payload, status),
    )
    return YouTubeClient(api_key="test-key")

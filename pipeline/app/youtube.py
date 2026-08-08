"""YouTube Data API v3 최소 클라이언트 (FR-6).

쿼터가 유한하므로(일 10,000유닛) 호출마다 사용량을 누적해 노출한다.
본격적인 쿼터 예산 관리와 배치 수집은 M2에서 이 위에 얹는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"

# 호출당 쿼터 비용 (YouTube 공식 기준)
COST_SEARCH = 100
COST_LIST = 1

REQUEST_TIMEOUT_S = 20


class YouTubeApiError(RuntimeError):
    """API 호출이 실패한 경우."""


@dataclass
class YouTubeClient:
    """쿼터 사용량을 추적하는 API 클라이언트.

    Attributes:
        api_key: YouTube Data API v3 키. 로그·repr에 노출하지 않는다 (NFR-3).
        quota_used: 이 인스턴스가 지금까지 쓴 쿼터 유닛 합계.
    """

    api_key: str = field(repr=False)
    quota_used: int = 0

    def search_channels(
        self,
        query: str,
        *,
        max_results: int = 25,
        region_code: str = "KR",
        relevance_language: str = "ko",
    ) -> list[dict[str, Any]]:
        """검색어로 채널을 찾는다 (100유닛/회 — 예산제로만 호출할 것, D14).

        Args:
            query: 검색어.
            max_results: 최대 결과 수 (1~50).
            region_code: 검색 지역. 한국 채널 발굴이므로 기본 KR (D9).
            relevance_language: 결과 언어 선호도.

        Returns:
            `channelId`, `title`, `description`을 담은 dict 목록.
        """
        payload = self._get(
            "search",
            {
                "part": "snippet",
                "type": "channel",
                "q": query,
                "maxResults": max_results,
                "regionCode": region_code,
                "relevanceLanguage": relevance_language,
            },
            cost=COST_SEARCH,
        )
        results: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            channel_id = item.get("id", {}).get("channelId") or item.get("snippet", {}).get("channelId")
            if not channel_id:
                continue
            snippet = item.get("snippet", {})
            results.append(
                {
                    "channel_id": channel_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                }
            )
        return results

    def fetch_channels(self, channel_ids: list[str]) -> list[dict[str, Any]]:
        """채널 통계·메타를 배치로 읽는다 (50개당 1유닛).

        Args:
            channel_ids: 채널 id 목록. 50개 단위로 나눠 호출한다.

        Returns:
            채널 정보 dict 목록.
        """
        collected: list[dict[str, Any]] = []
        for batch in _chunks(channel_ids, 50):
            payload = self._get(
                "channels",
                {"part": "snippet,statistics,contentDetails", "id": ",".join(batch), "maxResults": 50},
                cost=COST_LIST,
            )
            for item in payload.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                collected.append(
                    {
                        "channel_id": item.get("id", ""),
                        "title": snippet.get("title", ""),
                        "description": snippet.get("description", ""),
                        "custom_url": snippet.get("customUrl", ""),
                        "country": snippet.get("country", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                        "subscriber_count": _to_int(stats.get("subscriberCount")),
                        "view_count": _to_int(stats.get("viewCount")),
                        "video_count": _to_int(stats.get("videoCount")),
                        "hidden_subscriber_count": bool(stats.get("hiddenSubscriberCount", False)),
                    }
                )
        return collected

    def _get(self, endpoint: str, params: dict[str, Any], *, cost: int) -> dict[str, Any]:
        """API를 호출하고 쿼터 사용량을 누적한다."""
        params = {**params, "key": self.api_key}
        try:
            response = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=REQUEST_TIMEOUT_S)
        except requests.RequestException as exc:
            raise YouTubeApiError(f"{endpoint} 호출 실패 — {exc}") from exc

        self.quota_used += cost

        if response.status_code != 200:
            reason = _error_reason(response)
            raise YouTubeApiError(f"{endpoint} 오류 (HTTP {response.status_code}, {reason})")

        data: dict[str, Any] = response.json()
        return data


def _chunks(items: list[str], size: int) -> list[list[str]]:
    """목록을 size 단위로 나눈다."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def _to_int(value: Any) -> int:
    """통계 문자열을 정수로 바꾼다 (숨김 처리된 값은 0)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _error_reason(response: requests.Response) -> str:
    """오류 응답에서 reason을 꺼낸다 (키 값은 노출하지 않는다)."""
    try:
        errors = response.json().get("error", {}).get("errors", [])
        return str(errors[0].get("reason", "unknown")) if errors else "unknown"
    except (ValueError, KeyError, IndexError):
        return "unknown"

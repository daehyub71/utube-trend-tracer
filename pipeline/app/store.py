"""Supabase 저장소 계층 (FR-6, NFR-1).

파이프라인은 service key로 접근한다 (RLS 우회). 웹은 이 계층을 쓰지 않는다 —
anon key로 `ut_trend_scores` 등 서빙 테이블만 읽는다 (NFR-3).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol


class SupabaseLike(Protocol):
    """테스트에서 가짜로 대체할 수 있도록 필요한 부분만 선언한다."""

    def table(self, name: str) -> Any: ...


class Store:
    """수집·산출 결과를 읽고 쓴다."""

    def __init__(self, client: SupabaseLike) -> None:
        self._client = client

    # ---- 채널 ----------------------------------------------------------------

    def upsert_channels(self, rows: Sequence[dict[str, Any]]) -> int:
        """채널 메타를 갱신한다."""
        if not rows:
            return 0
        self._client.table("ut_channels").upsert(list(rows), on_conflict="channel_id").execute()
        return len(rows)

    def tracked_channels(self) -> list[dict[str, Any]]:
        """추적 중인 채널 목록을 읽는다 (졸업된 채널 제외)."""
        result = (
            self._client.table("ut_channels")
            .select("channel_id,title,category_ids,is_seed,tracked,last_upload_at")
            .eq("tracked", True)
            .execute()
        )
        return list(getattr(result, "data", None) or [])

    def graduate_channels(self, channel_ids: Sequence[str], *, at: datetime) -> int:
        """채널 추적을 중단한다 (D11) — 삭제가 아니라 표시만 바꾼다."""
        if not channel_ids:
            return 0
        (
            self._client.table("ut_channels")
            .update({"tracked": False, "graduated_at": at.isoformat()})
            .in_("channel_id", list(channel_ids))
            .execute()
        )
        return len(channel_ids)

    def insert_channel_snapshots(self, rows: Sequence[dict[str, Any]]) -> int:
        """채널 스냅샷을 적재한다."""
        if not rows:
            return 0
        self._client.table("ut_channel_snapshots").insert(list(rows)).execute()
        return len(rows)

    # ---- 영상 ----------------------------------------------------------------

    def upsert_videos(self, rows: Sequence[dict[str, Any]]) -> int:
        """영상 메타를 갱신한다."""
        if not rows:
            return 0
        self._client.table("ut_videos").upsert(list(rows), on_conflict="video_id").execute()
        return len(rows)

    def insert_video_snapshots(self, rows: Sequence[dict[str, Any]]) -> int:
        """영상 스냅샷을 적재한다."""
        if not rows:
            return 0
        self._client.table("ut_video_snapshots").insert(list(rows)).execute()
        return len(rows)

    def recent_video_ids(self, since: datetime) -> list[str]:
        """추적 대상 영상 id를 읽는다 (업로드 시각 기준)."""
        result = (
            self._client.table("ut_videos")
            .select("video_id")
            .gte("published_at", since.isoformat())
            .execute()
        )
        return [str(r["video_id"]) for r in (getattr(result, "data", None) or [])]

    def delete_videos(self, video_ids: Sequence[str]) -> int:
        """삭제·비공개된 영상을 제거한다 (D12, 약관 요구)."""
        if not video_ids:
            return 0
        self._client.table("ut_videos").delete().in_("video_id", list(video_ids)).execute()
        return len(video_ids)

    # ---- 시계열 조회 (산출용) --------------------------------------------------

    def video_series(self, since: datetime) -> list[dict[str, Any]]:
        """영상 메타 + 스냅샷을 산출용으로 읽는다."""
        result = (
            self._client.table("ut_videos")
            .select(
                "video_id,channel_id,category_ids,is_short,published_at,unclassified,age_restricted,"
                "ut_video_snapshots(captured_at,view_count)"
            )
            .gte("published_at", since.isoformat())
            .execute()
        )
        return list(getattr(result, "data", None) or [])

    def channel_series(self) -> list[dict[str, Any]]:
        """채널 메타 + 스냅샷을 산출용으로 읽는다."""
        result = (
            self._client.table("ut_channels")
            .select(
                "channel_id,category_ids,unclassified,tracked,"
                "ut_channel_snapshots(captured_at,subscriber_count,view_count)"
            )
            .eq("tracked", True)
            .execute()
        )
        return list(getattr(result, "data", None) or [])

    # ---- 랭킹 ----------------------------------------------------------------

    def replace_trend_scores(self, rows: Sequence[dict[str, Any]], *, boards: Sequence[str]) -> int:
        """랭킹을 교체한다 — 이전 산출을 지우고 새로 넣는다.

        프론트가 읽는 유일한 소스이므로, 부분 갱신으로 옛 순위가 섞이지 않게 한다.
        """
        if boards:
            self._client.table("ut_trend_scores").delete().in_("board", list(boards)).execute()
        if not rows:
            return 0
        self._client.table("ut_trend_scores").insert(list(rows)).execute()
        return len(rows)

    # ---- 보관 정책 ------------------------------------------------------------

    def purge_before(self, cutoff: datetime) -> dict[str, int]:
        """30일이 지난 데이터를 지운다 (NFR-1).

        Returns:
            테이블별 삭제 시도 건수 (PostgREST가 개수를 주지 않으므로 실행 여부만 표시).
        """
        stamp = cutoff.isoformat()
        self._client.table("ut_video_snapshots").delete().lt("captured_at", stamp).execute()
        self._client.table("ut_channel_snapshots").delete().lt("captured_at", stamp).execute()
        self._client.table("ut_videos").delete().lt("published_at", stamp).execute()
        return {"video_snapshots": 1, "channel_snapshots": 1, "videos": 1}

    # ---- 실행 기록 ------------------------------------------------------------

    def start_run(self, at: datetime) -> int | None:
        """수집 실행을 기록하고 run_id를 돌려준다 (NFR-4, FR-9)."""
        result = self._client.table("ut_collect_runs").insert({"started_at": at.isoformat()}).execute()
        rows = getattr(result, "data", None) or []
        return int(rows[0]["run_id"]) if rows else None

    def finish_run(
        self,
        run_id: int | None,
        *,
        at: datetime,
        quota_used: int,
        videos_updated: int,
        channels_updated: int,
        errors: Sequence[str],
    ) -> None:
        """수집 실행 결과를 기록한다."""
        if run_id is None:
            return
        (
            self._client.table("ut_collect_runs")
            .update(
                {
                    "finished_at": at.isoformat(),
                    "quota_used": quota_used,
                    "videos_updated": videos_updated,
                    "channels_updated": channels_updated,
                    "errors": list(errors),
                }
            )
            .eq("run_id", run_id)
            .execute()
        )

    def quota_used_since(self, since: datetime) -> int:
        """오늘 이미 쓴 쿼터를 합산한다 — cron이 하루 3회 돌기 때문 (NFR-4)."""
        result = (
            self._client.table("ut_collect_runs")
            .select("quota_used")
            .gte("started_at", since.isoformat())
            .execute()
        )
        return sum(int(r.get("quota_used") or 0) for r in (getattr(result, "data", None) or []))

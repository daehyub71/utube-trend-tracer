"""4개 보드 랭킹 산출 테스트 (FR-2~5, FR-7, NFR-7).

보드마다 대상·α·필터가 다르다. 이 테스트가 그 차이를 고정한다.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.ranking import (
    ChannelSeries,
    VideoSeries,
    rank_rising_channels,
    rank_rising_videos,
    rank_trending_channels,
    rank_trending_videos,
)
from app.scoring import Snapshot

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def video(
    video_id: str,
    *,
    subscribers: int,
    views: list[tuple[float, int]],
    uploaded_days_ago: float = 1.0,
    is_short: bool = False,
    category_id: str = "food_domestic",
    channel_id: str = "UC1",
) -> VideoSeries:
    """`views` 는 (지금으로부터 몇 시간 전, 조회수) 목록."""
    return VideoSeries(
        video_id=video_id,
        channel_id=channel_id,
        category_id=category_id,
        subscribers=subscribers,
        is_short=is_short,
        published_at=NOW - timedelta(days=uploaded_days_ago),
        snapshots=[Snapshot(captured_at=NOW - timedelta(hours=h), value=v) for h, v in views],
    )


def channel(
    channel_id: str,
    *,
    subscribers: int,
    series: list[tuple[float, int]],
    category_id: str = "food_domestic",
    measure: str = "subscribers",
) -> ChannelSeries:
    return ChannelSeries(
        channel_id=channel_id,
        category_id=category_id,
        subscribers=subscribers,
        snapshots=[Snapshot(captured_at=NOW - timedelta(hours=h), value=v) for h, v in series],
        measure=measure,
    )


class TestTrendingVideos:
    def test_ranks_by_view_velocity(self) -> None:
        items = [
            video("slow", subscribers=100_000, views=[(48, 1_000), (0, 5_000)]),
            video("fast", subscribers=100_000, views=[(48, 1_000), (0, 90_000)]),
        ]

        ranked = rank_trending_videos(items, now=NOW)

        assert [r.entity_id for r in ranked] == ["fast", "slow"]
        assert ranked[0].rank == 1

    def test_excludes_videos_older_than_seven_days(self) -> None:
        """오래된 영상이 누적 조회수로 눌러앉지 않게 한다 (FR-7)."""
        items = [
            video("fresh", subscribers=10_000, views=[(48, 0), (0, 10_000)], uploaded_days_ago=2),
            video("old", subscribers=10_000, views=[(48, 0), (0, 999_999)], uploaded_days_ago=9),
        ]

        ranked = rank_trending_videos(items, now=NOW)

        assert [r.entity_id for r in ranked] == ["fresh"]

    def test_applies_shorts_beta(self) -> None:
        """같은 성과라면 Shorts가 β만큼 낮게 잡힌다 (D8)."""
        items = [
            video("regular", subscribers=10_000, views=[(24, 0), (0, 50_000)]),
            video("short", subscribers=10_000, views=[(24, 0), (0, 50_000)], is_short=True),
        ]

        ranked = rank_trending_videos(items, now=NOW)

        assert [r.entity_id for r in ranked] == ["regular", "short"]
        assert ranked[1].score == pytest.approx(ranked[0].score * 0.5)

    def test_groups_by_category(self) -> None:
        """랭킹은 카테고리별로 매겨진다 (보드는 카테고리 안에서 순위)."""
        items = [
            video("food1", subscribers=10_000, views=[(24, 0), (0, 10_000)], category_id="food_domestic"),
            video("trav1", subscribers=10_000, views=[(24, 0), (0, 5_000)], category_id="travel_domestic"),
        ]

        ranked = rank_trending_videos(items, now=NOW)

        by_category = {r.category_id: r for r in ranked}
        assert by_category["food_domestic"].rank == 1
        assert by_category["travel_domestic"].rank == 1  # 각 카테고리에서 1위

    def test_skips_series_with_single_snapshot(self) -> None:
        """스냅샷이 하나뿐이면 증가량을 알 수 없다 — 콜드스타트 구간 (NFR-7)."""
        ranked = rank_trending_videos([video("only", subscribers=1_000, views=[(0, 500)])], now=NOW)

        assert ranked == []

    def test_uses_widest_window_within_range(self) -> None:
        """구간 안에서 가장 이른 스냅샷과 최신을 쓴다 — 결측이 있어도 계산된다 (NFR-7)."""
        items = [
            video("gap", subscribers=10_000, views=[(46, 1_000), (0, 21_000)]),  # 중간 결측
        ]

        ranked = rank_trending_videos(items, now=NOW)

        assert len(ranked) == 1
        assert ranked[0].score > 0


class TestRisingVideos:
    def test_uses_alpha_one_so_small_channels_compete(self) -> None:
        """구독자 대비 성과 — 소형 채널의 '터진 영상'이 상위로 온다 (FR-3)."""
        items = [
            video("big", subscribers=1_000_000, views=[(24, 0), (0, 200_000)]),
            video("small", subscribers=8_000, views=[(24, 0), (0, 120_000)]),
        ]

        ranked = rank_rising_videos(items, now=NOW)

        assert ranked[0].entity_id == "small"

    def test_still_limits_to_seven_days(self) -> None:
        items = [video("old", subscribers=1_000, views=[(24, 0), (0, 50_000)], uploaded_days_ago=10)]

        assert rank_rising_videos(items, now=NOW) == []


class TestTrendingChannels:
    def test_ranks_by_view_growth(self) -> None:
        items = [
            channel("UCa", subscribers=100_000, series=[(168, 1_000_000), (0, 1_100_000)], measure="views"),
            channel("UCb", subscribers=100_000, series=[(168, 1_000_000), (0, 1_010_000)], measure="views"),
        ]

        ranked = rank_trending_channels(items, now=NOW)

        assert [r.entity_id for r in ranked] == ["UCa", "UCb"]


class TestRisingChannels:
    def test_excludes_channels_above_subscriber_threshold(self) -> None:
        """구독자 10만 초과 채널은 제외한다 (D7)."""
        items = [
            channel("small", subscribers=50_000, series=[(168, 40_000), (0, 50_000)]),
            channel("big", subscribers=500_000, series=[(168, 400_000), (0, 500_000)]),
        ]

        ranked = rank_rising_channels(items, now=NOW)

        assert [r.entity_id for r in ranked] == ["small"]

    def test_boundary_of_one_hundred_thousand_is_included(self) -> None:
        """'10만 이하'이므로 정확히 10만은 포함된다."""
        items = [channel("exact", subscribers=100_000, series=[(168, 90_000), (0, 100_000)])]

        assert len(rank_rising_channels(items, now=NOW)) == 1

    def test_measures_subscriber_delta(self) -> None:
        """신규 뜨는 유튜버는 Δ구독자를 잰다 (FR-7 표)."""
        items = [
            channel("grew", subscribers=20_000, series=[(168, 10_000), (0, 20_000)]),
            channel("flat", subscribers=20_000, series=[(168, 19_900), (0, 20_000)]),
        ]

        ranked = rank_rising_channels(items, now=NOW)

        assert ranked[0].entity_id == "grew"


class TestRowOutput:
    def test_row_matches_trend_scores_schema(self) -> None:
        """산출 행이 ut_trend_scores 컬럼과 맞아야 한다."""
        ranked = rank_trending_videos(
            [video("v", subscribers=10_000, views=[(24, 0), (0, 5_000)])], now=NOW
        )

        row = ranked[0].to_row()

        assert set(row) == {
            "board", "category_id", "entity_id", "score", "rank",
            "computed_at", "window_start", "window_end",
        }
        assert row["board"] == "trending_videos"

    def test_window_reflects_actual_snapshots(self) -> None:
        """윈도우는 실제 사용한 스냅샷 시각이다 (Δ시간 실측의 근거)."""
        ranked = rank_trending_videos(
            [video("v", subscribers=10_000, views=[(30, 0), (0, 5_000)])], now=NOW
        )

        row = ranked[0].to_row()
        assert row["window_end"] == NOW.isoformat()
        assert row["window_start"] == (NOW - timedelta(hours=30)).isoformat()

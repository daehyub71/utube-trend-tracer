import { supabase } from "./supabase";
import type {
  BoardEntry,
  BoardId,
  BoardResult,
  Category,
  ChannelDetail,
  SeriesPoint,
} from "./types";
import { VIDEO_BOARDS } from "./types";

/**
 * 프론트는 산출된 랭킹 캐시만 읽는다 (NFR-3).
 *
 * 조회는 anon key + RLS 읽기 전용으로만 이뤄지며, 요청 시 계산하거나
 * YouTube API를 부르는 경로는 없다.
 *
 * 모든 조회는 실패를 던지지 않고 빈 결과 + error 문자열로 돌려준다 —
 * DB가 죽어도 화면 전체가 함께 죽으면 안 된다 (NFR-9와 같은 원칙).
 */

const BOARD_LIMIT = 20;
const CHANNEL_SERIES_DAYS = 30;

export async function fetchCategories(): Promise<Category[]> {
  const { data, error } = await supabase
    .from("ut_categories")
    .select("id,name,parent,tag")
    .eq("enabled", true)
    .order("id");

  if (error || !data) return [];
  return data as Category[];
}

/** 카테고리 하나의 보드 4개를 모두 읽는다. */
export async function fetchBoards(categoryId: string, boards: BoardId[]): Promise<BoardResult[]> {
  return Promise.all(boards.map((board) => fetchBoard(categoryId, board)));
}

export async function fetchBoard(categoryId: string, board: BoardId): Promise<BoardResult> {
  const empty: BoardResult = { board, entries: [], computedAt: null, error: null };

  const { data, error } = await supabase
    .from("ut_trend_scores")
    .select("entity_id,score,rank,computed_at")
    .eq("board", board)
    .eq("category_id", categoryId)
    .order("rank")
    .limit(BOARD_LIMIT);

  if (error) return { ...empty, error: "랭킹을 불러오지 못했습니다." };
  if (!data || data.length === 0) return empty;

  const ids = data.map((row) => String(row.entity_id));
  const computedAt = data[0]?.computed_at ? String(data[0].computed_at) : null;

  try {
    const entries = VIDEO_BOARDS.includes(board)
      ? await hydrateVideos(data, ids)
      : await hydrateChannels(data, ids);
    return { board, entries, computedAt, error: null };
  } catch {
    return { ...empty, computedAt, error: "항목 정보를 불러오지 못했습니다." };
  }
}

type ScoreRow = { entity_id: unknown; score: unknown; rank: unknown; computed_at: unknown };

async function hydrateVideos(rows: ScoreRow[], ids: string[]): Promise<BoardEntry[]> {
  const { data: videos } = await supabase
    .from("ut_videos")
    .select("video_id,channel_id,title,thumbnail_url,published_at,is_short")
    .in("video_id", ids);

  const channelIds = [...new Set((videos ?? []).map((v) => String(v.channel_id)))];
  const channelMap = await fetchChannelSummaries(channelIds);
  const videoMap = new Map((videos ?? []).map((v) => [String(v.video_id), v]));
  const viewMap = await fetchLatestViewCounts(ids);

  return rows.flatMap((row) => {
    const video = videoMap.get(String(row.entity_id));
    if (!video) return []; // 삭제된 영상 — 다음 수집 주기에 랭킹에서도 사라진다 (D12)
    const channel = channelMap.get(String(video.channel_id));
    return [
      {
        rank: Number(row.rank),
        score: Number(row.score),
        entityId: String(row.entity_id),
        video: {
          title: String(video.title ?? ""),
          thumbnailUrl: video.thumbnail_url ? String(video.thumbnail_url) : null,
          publishedAt: String(video.published_at ?? ""),
          isShort: Boolean(video.is_short),
          channelId: String(video.channel_id),
          channelTitle: channel?.title ?? "",
          viewCount: viewMap.get(String(row.entity_id)) ?? null,
          subscriberCount: channel?.subscriberCount ?? null,
        },
      },
    ];
  });
}

async function hydrateChannels(rows: ScoreRow[], ids: string[]): Promise<BoardEntry[]> {
  const summaries = await fetchChannelSummaries(ids);

  return rows.flatMap((row) => {
    const channel = summaries.get(String(row.entity_id));
    if (!channel) return [];
    return [
      {
        rank: Number(row.rank),
        score: Number(row.score),
        entityId: String(row.entity_id),
        channel: {
          title: channel.title,
          thumbnailUrl: channel.thumbnailUrl,
          subscriberCount: channel.subscriberCount,
          growthRate: channel.growthRate,
        },
      },
    ];
  });
}

interface ChannelSummary {
  title: string;
  thumbnailUrl: string | null;
  subscriberCount: number | null;
  growthRate: number | null;
}

async function fetchChannelSummaries(ids: string[]): Promise<Map<string, ChannelSummary>> {
  if (ids.length === 0) return new Map();

  const { data: channels } = await supabase
    .from("ut_channels")
    .select("channel_id,title,thumbnail_url")
    .in("channel_id", ids);

  const { data: snapshots } = await supabase
    .from("ut_channel_snapshots")
    .select("channel_id,captured_at,subscriber_count")
    .in("channel_id", ids)
    .order("captured_at", { ascending: true });

  const byChannel = new Map<string, { first: number; last: number }>();
  for (const snap of snapshots ?? []) {
    const key = String(snap.channel_id);
    const value = Number(snap.subscriber_count ?? 0);
    const existing = byChannel.get(key);
    byChannel.set(key, existing ? { first: existing.first, last: value } : { first: value, last: value });
  }

  return new Map(
    (channels ?? []).map((channel) => {
      const key = String(channel.channel_id);
      const range = byChannel.get(key);
      const growthRate =
        range && range.first > 0 ? (range.last - range.first) / range.first : null;
      return [
        key,
        {
          title: String(channel.title ?? ""),
          thumbnailUrl: channel.thumbnail_url ? String(channel.thumbnail_url) : null,
          subscriberCount: range?.last ?? null,
          growthRate,
        },
      ];
    })
  );
}

async function fetchLatestViewCounts(videoIds: string[]): Promise<Map<string, number>> {
  if (videoIds.length === 0) return new Map();

  const { data } = await supabase
    .from("ut_video_snapshots")
    .select("video_id,captured_at,view_count")
    .in("video_id", videoIds)
    .order("captured_at", { ascending: true });

  const latest = new Map<string, number>();
  for (const row of data ?? []) {
    latest.set(String(row.video_id), Number(row.view_count ?? 0));
  }
  return latest;
}

export async function fetchChannelDetail(channelId: string): Promise<ChannelDetail | null> {
  const { data: channel, error } = await supabase
    .from("ut_channels")
    .select("channel_id,title,thumbnail_url,category_ids")
    .eq("channel_id", channelId)
    .maybeSingle();

  if (error || !channel) return null;

  const since = new Date(Date.now() - CHANNEL_SERIES_DAYS * 86_400_000).toISOString();
  const { data: snapshots } = await supabase
    .from("ut_channel_snapshots")
    .select("captured_at,subscriber_count,view_count")
    .eq("channel_id", channelId)
    .gte("captured_at", since)
    .order("captured_at", { ascending: true });

  const subscriberSeries: SeriesPoint[] = (snapshots ?? []).map((s) => ({
    capturedAt: String(s.captured_at),
    value: Number(s.subscriber_count ?? 0),
  }));
  const viewSeries: SeriesPoint[] = (snapshots ?? []).map((s) => ({
    capturedAt: String(s.captured_at),
    value: Number(s.view_count ?? 0),
  }));

  return {
    channelId: String(channel.channel_id),
    title: String(channel.title ?? ""),
    thumbnailUrl: channel.thumbnail_url ? String(channel.thumbnail_url) : null,
    categoryIds: (channel.category_ids ?? []) as string[],
    subscriberCount: subscriberSeries.at(-1)?.value ?? null,
    subscriberSeries,
    viewSeries,
    recentVideos: await fetchChannelRecentVideos(channelId),
  };
}

async function fetchChannelRecentVideos(channelId: string): Promise<BoardEntry[]> {
  const { data: videos } = await supabase
    .from("ut_videos")
    .select("video_id,channel_id,title,thumbnail_url,published_at,is_short")
    .eq("channel_id", channelId)
    .eq("unclassified", false)
    .order("published_at", { ascending: false })
    .limit(5);

  if (!videos || videos.length === 0) return [];
  const viewMap = await fetchLatestViewCounts(videos.map((v) => String(v.video_id)));

  return videos.map((video, index) => ({
    rank: index + 1,
    score: 0,
    entityId: String(video.video_id),
    video: {
      title: String(video.title ?? ""),
      thumbnailUrl: video.thumbnail_url ? String(video.thumbnail_url) : null,
      publishedAt: String(video.published_at ?? ""),
      isShort: Boolean(video.is_short),
      channelId,
      channelTitle: "",
      viewCount: viewMap.get(String(video.video_id)) ?? null,
      subscriberCount: null,
    },
  }));
}

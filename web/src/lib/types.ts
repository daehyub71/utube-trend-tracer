/** 4개 랭킹 보드 (SPEC FR-2~5). */
export type BoardId =
  | "trending_videos"
  | "rising_videos"
  | "trending_channels"
  | "rising_channels";

export const BOARD_META: Record<BoardId, { title: string; hint: string; tone: "heat" | "accent" }> = {
  trending_videos: {
    title: "지금 뜨는 영상",
    hint: "최근 7일 업로드 · 조회수 증가 속도",
    tone: "heat",
  },
  rising_videos: {
    title: "신규 뜨는 영상",
    hint: "구독자 규모 대비 성과",
    tone: "heat",
  },
  trending_channels: {
    title: "지금 뜨는 유튜버",
    hint: "주간 조회수 성장",
    tone: "accent",
  },
  rising_channels: {
    title: "신규 뜨는 유튜버",
    hint: "구독 10만 이하 · 구독자 성장",
    tone: "accent",
  },
};

export const VIDEO_BOARDS: BoardId[] = ["trending_videos", "rising_videos"];

export interface Category {
  id: string;
  name: string;
  parent: string;
  tag: "domestic" | "overseas";
}

/** 보드 한 줄 — 영상이면 video 필드가, 채널이면 channel 필드가 채워진다. */
export interface BoardEntry {
  rank: number;
  score: number;
  entityId: string;
  video?: {
    title: string;
    thumbnailUrl: string | null;
    publishedAt: string;
    isShort: boolean;
    channelId: string;
    channelTitle: string;
    viewCount: number | null;
    subscriberCount: number | null;
  };
  channel?: {
    title: string;
    thumbnailUrl: string | null;
    subscriberCount: number | null;
    growthRate: number | null;
  };
}

/** 보드 하나의 조회 결과 — 실패해도 화면 전체가 죽지 않도록 상태를 함께 담는다. */
export interface BoardResult {
  board: BoardId;
  entries: BoardEntry[];
  computedAt: string | null;
  error: string | null;
}

export interface ChannelDetail {
  channelId: string;
  title: string;
  thumbnailUrl: string | null;
  categoryIds: string[];
  subscriberCount: number | null;
  subscriberSeries: SeriesPoint[];
  viewSeries: SeriesPoint[];
  recentVideos: BoardEntry[];
}

export interface SeriesPoint {
  capturedAt: string;
  value: number;
}

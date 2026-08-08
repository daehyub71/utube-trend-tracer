-- utube-trend-tracer 스키마 (SPEC §6, PLAN §3)
-- 모든 테이블은 ut_ 접두어 — 다른 프로젝트와 Supabase 인스턴스 공유 대비.
-- 적용: Supabase SQL Editor에서 전체 실행 (멱등 — if not exists).

-- 카테고리 정의 (config/categories.yaml에서 동기화)
create table if not exists ut_categories (
  id          text primary key,              -- 예: 'food_domestic'
  name        text not null,                 -- 예: '음식 > 국내'
  parent      text not null,                 -- 대분류: food/travel/tech/aicoding/vlog/fitness
  tag         text not null check (tag in ('domestic', 'overseas')),  -- 소재 구분 (D9)
  keywords    text[] not null default '{}',
  weight      numeric not null default 1.0,  -- 예: 바이브코딩·AI 1.1
  enabled     boolean not null default true,
  updated_at  timestamptz not null default now()
);

-- 추적 채널 (한국 채널만, D9)
create table if not exists ut_channels (
  channel_id     text primary key,
  title          text not null,
  thumbnail_url  text,
  category_ids   text[] not null default '{}',
  unclassified   boolean not null default false,   -- 랭킹 제외 (D10)
  is_seed        boolean not null default false,
  tracked        boolean not null default true,    -- false = 졸업 (D11)
  graduated_at   timestamptz,
  last_upload_at timestamptz,
  first_seen_at  timestamptz not null default now()
);

-- 채널 스냅샷 시계열 (30일 롤링)
create table if not exists ut_channel_snapshots (
  id               bigint generated always as identity primary key,
  channel_id       text not null references ut_channels (channel_id) on delete cascade,
  captured_at      timestamptz not null default now(),
  subscriber_count bigint not null,
  view_count       bigint not null,
  video_count      integer not null
);
create index if not exists idx_ut_channel_snapshots_channel_time
  on ut_channel_snapshots (channel_id, captured_at);

-- 영상 메타 (30일 롤링)
create table if not exists ut_videos (
  video_id       text primary key,
  channel_id     text not null references ut_channels (channel_id) on delete cascade,
  title          text not null,
  thumbnail_url  text,
  published_at   timestamptz not null,
  duration_s     integer,
  is_short       boolean not null default false,   -- ≤3분 (D8)
  age_restricted boolean not null default false,   -- 랭킹 제외 (D12)
  category_ids   text[] not null default '{}',
  unclassified   boolean not null default false    -- 랭킹 제외 (D10)
);

-- 영상 스냅샷 시계열 (30일 롤링, 용량 지배 항목)
create table if not exists ut_video_snapshots (
  id          bigint generated always as identity primary key,
  video_id    text not null references ut_videos (video_id) on delete cascade,
  captured_at timestamptz not null default now(),
  view_count  bigint not null
);
create index if not exists idx_ut_video_snapshots_video_time
  on ut_video_snapshots (video_id, captured_at);

-- 산출 랭킹 캐시 — 프론트가 읽는 유일한 랭킹 소스
create table if not exists ut_trend_scores (
  id           bigint generated always as identity primary key,
  board        text not null check (board in
                 ('trending_videos', 'rising_videos', 'trending_channels', 'rising_channels')),
  category_id  text not null references ut_categories (id),
  entity_id    text not null,                -- video_id 또는 channel_id
  score        double precision not null,
  rank         integer not null,
  computed_at  timestamptz not null default now(),
  window_start timestamptz not null,
  window_end   timestamptz not null
);
create index if not exists idx_ut_trend_scores_board_cat_time
  on ut_trend_scores (board, category_id, computed_at desc);

-- 수집 실행 기록 (admin 리포트·쿼터 추적, NFR-4)
create table if not exists ut_collect_runs (
  run_id           bigint generated always as identity primary key,
  started_at       timestamptz not null default now(),
  finished_at      timestamptz,
  quota_used       integer not null default 0,
  videos_updated   integer not null default 0,
  channels_updated integer not null default 0,
  errors           jsonb not null default '[]'
);

-- RLS: 파이프라인은 service key(RLS 우회), 웹(anon)은 서빙 테이블 읽기만 (PLAN P3)
alter table ut_categories        enable row level security;
alter table ut_channels          enable row level security;
alter table ut_channel_snapshots enable row level security;
alter table ut_videos            enable row level security;
alter table ut_video_snapshots   enable row level security;
alter table ut_trend_scores      enable row level security;
alter table ut_collect_runs      enable row level security;  -- anon 정책 없음 = 웹 접근 불가

drop policy if exists ut_anon_read_categories        on ut_categories;
drop policy if exists ut_anon_read_channels          on ut_channels;
drop policy if exists ut_anon_read_channel_snapshots on ut_channel_snapshots;
drop policy if exists ut_anon_read_videos            on ut_videos;
drop policy if exists ut_anon_read_video_snapshots   on ut_video_snapshots;
drop policy if exists ut_anon_read_trend_scores      on ut_trend_scores;

-- anon key는 브라우저 번들에 공개되므로 누구나 PostgREST를 직접 호출할 수 있다.
-- 따라서 "웹 UI가 안 보여준다"는 보호가 아니며, 노출하지 않기로 한 행은 정책에서 막는다.
create policy ut_anon_read_categories on ut_categories for select to anon using (enabled);

-- 졸업(추적 중단)한 채널은 서빙 대상이 아니다.
create policy ut_anon_read_channels on ut_channels for select to anon using (tracked);

-- 연령제한·미분류 영상은 랭킹에서 빼는 것으로 끝나면 안 된다 (D12, D10) —
-- 원본 행이 읽히면 제3자가 그 목록만 골라 덤프할 수 있다.
create policy ut_anon_read_videos on ut_videos for select to anon
  using (not age_restricted and not unclassified);

-- 스냅샷은 위 정책을 통과한 부모 행에 대해서만 읽히게 한다.
-- 바깥 테이블을 반드시 한정한다 — `c.channel_id = channel_id` 로 쓰면 안쪽 컬럼끼리
-- 비교되어 조건이 항상 참이 되고, 정책이 조용히 무력해진다.
create policy ut_anon_read_channel_snapshots on ut_channel_snapshots for select to anon
  using (
    exists (
      select 1 from ut_channels c
      where c.channel_id = ut_channel_snapshots.channel_id and c.tracked
    )
  );

create policy ut_anon_read_video_snapshots on ut_video_snapshots for select to anon
  using (
    exists (
      select 1 from ut_videos v
      where v.video_id = ut_video_snapshots.video_id
        and not v.age_restricted
        and not v.unclassified
    )
  );

create policy ut_anon_read_trend_scores on ut_trend_scores for select to anon using (true);

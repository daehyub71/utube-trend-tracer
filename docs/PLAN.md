# PLAN — utube-trend-tracer

> **상태: 확정 (v1.0, 2026-08-08) — P1~P4 전체 채택 (§7).** 변경 시 SPEC → PLAN → TASKS 역추적 갱신.
> 기준 문서: [SPEC.md](SPEC.md) v1.1 (D1~D14 확정)

## 1. 아키텍처 개요

```
GitHub Actions cron (하루 3회, KST 기준 분산)
 └─ pipeline (Python)
     1. RSS 폴링 → 추적 채널 새 영상 감지 (쿼터 0)
     2. videos.list / channels.list 배치 → 스냅샷 적재
     3. 키워드 분류 (categories.yaml) → 미분류는 랭킹 제외 플래그
     4. 트렌드 지수 산출 (velocity + α/β) → ut_trend_scores 갱신
     5. 30일 롤링 purge + 졸업 처리 + 삭제·비공개 반영
     6. admin 리포트 생성 (마크다운, 리포 커밋)
          │
          ▼
 Supabase (Postgres 무료 티어)
          │  (읽기 전용, ut_trend_scores 중심)
          ▼
 Vercel (Next.js App Router) — 홈 4보드 + 채널 상세 + 정책 페이지
```

**핵심 원칙**
- 프론트는 **산출 캐시(`ut_trend_scores`)만 조회** — 요청 시 계산 없음, API 키 접근 없음 (NFR-3).
- YouTube API 키는 GitHub Actions Secrets + 로컬 `.env`에만 존재.
- 파이프라인은 Supabase **service key**, 웹은 **anon key + RLS 읽기 전용** 분리.
- 파이프라인 어느 단계가 실패해도 이전 산출물로 서빙 지속 (NFR-7), admin 리포트에 실패 표시 (NFR-9).

## 2. 디렉토리 구조 (모노리포)

```
utube-trend-tracer/
├── CLAUDE.md              # 프로젝트 규칙 (M0에서 작성)
├── docs/                  # SPEC / PLAN / DESIGN / TASKS
├── config/                # 코드 수정 없이 갱신 가능한 운영 데이터 (FR-1, FR-10)
│   ├── categories.yaml    # 카테고리 정의 + 매핑 키워드 + 가중치
│   ├── seeds.yaml         # 시드 채널 (카테고리별 10~20개, 국내/해외 태그 포함)
│   └── blocklist.yaml     # 수동 차단 리스트 (채널/영상)
├── pipeline/              # Python 수집·산출 (venv, requirements.txt)
│   ├── app/               # 소스 (mypy 대상)
│   └── tests/             # pytest
├── web/                   # Next.js (App Router, TS, Tailwind)
└── .github/workflows/
    └── collect.yml        # cron 수집 + 검증 + admin 리포트
```

## 3. 데이터 모델 상세 (Supabase)

**모든 테이블은 `ut_` 접두어 (SPEC §6, 2026-08-08)** — 기존 프로젝트와 Supabase 인스턴스를 공유해도 충돌하지 않게.

| 테이블 | 주요 컬럼 | 비고 |
|--------|-----------|------|
| `ut_categories` | id, name, parent, tag(국내/해외), keywords[], weight, enabled | config/categories.yaml에서 동기화 |
| `ut_channels` | channel_id PK, title, thumbnail_url, category_ids[], is_seed, tracked, graduated_at, last_upload_at, first_seen_at | tracked=false = 졸업 (D11) |
| `ut_channel_snapshots` | channel_id, captured_at, subscriber_count, view_count, video_count | 30일 롤링 |
| `ut_videos` | video_id PK, channel_id, title, published_at, duration_s, is_short, age_restricted, category_ids[], unclassified | is_short: ≤3분 (D8) |
| `ut_video_snapshots` | video_id, captured_at, view_count | 30일 롤링, 용량 지배 항목 |
| `ut_trend_scores` | board(4종), category_id, entity_id, score, rank, computed_at, window_start/end | 프론트가 읽는 유일한 랭킹 소스 |
| `ut_collect_runs` | run_id, started_at, quota_used, videos_updated, errors | admin 리포트·쿼터 추적 (NFR-4) |

**용량 추정 (상한 2,000채널 기준)**: ut_video_snapshots가 지배 —
추적 영상 약 6,000개(채널당 30일 내 ~3개) × 하루 3스냅샷 × 30일 ≈ 54만 행 ≈ 수십 MB. 500MB 한도 내 여유. M2에서 실측 후 재검증.

## 4. 마일스톤

| 단계 | 범위 | 완료 기준 |
|------|------|-----------|
| **M0 셋업** | 디렉토리 구조, venv/Next 스캐폴드, Supabase 프로젝트·스키마 마이그레이션, 프로젝트 CLAUDE.md, .env/.gitignore, CI 뼈대 | 로컬에서 pipeline·web 빈 실행 성공, 스키마 적용 확인 |
| **M1 분류·시드** | categories.yaml 스키마 + 키워드 분류기(TDD), 미분류 플래그, 시드 채널 수집·검증(RSS 확인), config→DB 동기화 | 분류기 테스트 통과, 시드 6카테고리×10개 이상 등재 |
| **M2 수집 파이프라인** | RSS 감지, videos/channels 스냅샷 배치, 쿼터 트래커, 30일 purge, 삭제·비공개 반영, 졸업 로직, Actions cron 가동 | cron 3회/일 자동 실행 성공, 쿼터 로그 확인 — **가동 시점부터 콜드스타트 2주 시계 시작** |
| **M3 지수 산출** | velocity 산식(α 0.25/1.0), Shorts β 보정, Δ시간 실측, 결측 보정, ut_trend_scores 적재 | 산식 규약 테스트(α≥1.0 관계 강제, SPEC FR-7) 포함 전체 통과 |
| **M4 웹 프론트** | **DESIGN.md 합의 선행** → 홈 4보드, 채널 상세(30일 그래프), 기준 시각 표시, 라이트/다크, 정책 페이지(자체 지표 명시·opt-out) | Vitest + build 통과, DESIGN 합의 기록 존재 |
| **M5 admin·안전** | admin 리포트(자동 점검 9종 + 미분류율·채널 수), blocklist 적용, 연령제한 제외, 런북 | 리포트가 cron 후 자동 커밋, 차단 항목 랭킹 제외 확인 |
| **M6 교정·오픈** | 콜드스타트 2주 데이터로 β(필요시 α) 교정 시연, 보안 점검 게이트(NFR-5), Vercel 배포·오픈 | 교정 기록 SPEC 반영, 보안 점검 통과, 공개 URL 동작 |

M2 완료 후 수집이 돌기 시작하므로 **M3~M5는 콜드스타트 2주와 병행** — 오픈 전 대기 시간이 낭비되지 않는다.

## 5. 테스트 전략 (TDD)

- **순수 로직 우선 (테스트 먼저)**: 키워드 분류기, 점수 산식(α/β), Δ시간 실측 계산, purge 대상 선정, 졸업 선정, 쿼터 예산 판단.
- **산식 규약 테스트**: `score ∝ 구독자^(1-α)` 관계를 고정 픽스처로 강제 — α<1이 "신규 뜨는" 보드에 들어오면 실패 (SPEC FR-7).
- **API mock**: YouTube 응답·RSS는 픽스처 JSON/XML로 대체, 네트워크 없는 테스트.
- **웹**: 보드/카드 컴포넌트 렌더링, 기준 시각 표시, 카테고리 전환 — Vitest.
- **CI**: PR마다 `ruff + mypy + pytest` (pipeline), `lint + vitest + build` (web).

## 6. 리스크

| 리스크 | 대응 |
|--------|------|
| 쿼터 초과 | 예산제(D14) + 쿼터 트래커가 임계 도달 시 수집 중단 (NFR-4) — 서빙 무영향 |
| Supabase 500MB 초과 | 30일 롤링 + 상한 2,000 (D11) + admin 용량 점검, M2 실측으로 추정 재검증 |
| 키워드 분류 정확도 낮음 | 미분류율 admin 노출 (D10) — 30%×2주 트리거로 LLM 분류 Phase 판단 |
| β=0.5 부정확 (Shorts 도배/과소노출) | M6 실데이터 교정 시연을 완료 조건으로 명시 |
| cron 지연·중복 실행 | Δ시간 실측(FR-7) + run 단위 잠금, 수집 공백은 결측 보정 |
| RSS 미지원·누락 채널 | 시드 등록 시 RSS 검증(M1), 실패 채널은 admin 리포트 표시 |
| Vercel 빌드 환경 차이 (Windows 교차 작업) | 파일명 ASCII 규칙 준수, lockfile 커밋, CI에서 build 검증 |

## 7. 토론 항목 결정 기록 (2026-08-08 사용자 확정)

- P1. ✅ 모노리포 구조 (§2) — pipeline/ + web/ 한 리포 (seoul-subway-analytics와 동일 패턴)
- P2. ✅ 지수 산출은 수집 cron 마지막 단계에서 배치 산출
- P3. ✅ Supabase 키 분리 — 파이프라인 service key / 웹 anon key + RLS 읽기 전용
- P4. ✅ 마일스톤 M0~M6 — M2를 앞당겨 콜드스타트 2주를 M3~M5와 병행

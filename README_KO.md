# utube-trend-tracer

> [English README](README.md)

카테고리별 유튜브 트렌드 발견 서비스.

유튜브가 2025년 7월 공식 인기 급상승 페이지를 없앤 뒤, "요즘 음식 쪽에서 뭐가 뜨는가"를
알려주는 API는 존재하지 않게 됐다. 이 서비스는 채널·영상 지표를 주기적으로 기록해
그 신호를 직접 계산한다.

## 무엇을 하는가

카테고리(음식·여행·IT테크·바이브코딩AI·브이로그·운동, 각각 국내/해외 소재로 나뉨)를 고르면
네 개의 랭킹이 나온다.

| 보드 | 측정 | 목적 |
|------|------|------|
| 지금 뜨는 영상 | 조회수 증가 속도, 업로드 7일 이내 | 지금 오르고 있는 것 |
| 신규 뜨는 영상 | 구독자 규모 대비 조회수 속도 | 소형 채널의 터진 영상 |
| 지금 뜨는 유튜버 | 주간 조회수 성장 | 상승세를 탄 채널 |
| 신규 뜨는 유튜버 | 구독자 성장, 10만 이하 | 주목할 신인 |

모든 순위에는 유튜브 공식 지표가 아닌 자체 산출값임을 표기한다.

## 점수는 어떻게 나오는가

```
점수 = Δ값 / (Δ시간h × max(구독자, 1000)^α)
```

지수 `α`가 두 종류의 보드를 가른다.

- **지금 뜨는**은 `α = 0.25` — 절대 규모를 반영하되 완만한 핸디캡만 준다.
- **신규 뜨는**은 `α = 1.0` — 점수가 규모와 무관해진다. 구독자 8천인 채널과 80만인 채널이
  같은 기준으로 겨룬다.

**신규 보드의 `α ≥ 1.0`은 규약이며 테스트가 강제한다.** Δ가 구독자에 비례할 때
`점수 ∝ 구독자^(1-α)` 이므로, α가 1보다 작으면 "신규 뜨는"이 조용히 규모 순으로 되돌아간다.
초기에 α=0.7로 시연했을 때 실제로 그랬고, 그 실패를 회귀 테스트로 남겨뒀다.

실무에서 중요한 두 가지가 더 있다.

- **Δ시간은 예정된 cron 시각이 아니라 실제 스냅샷 시각으로 잰다.** GitHub Actions는 수십 분
  늦을 수 있어서, 예정 간격을 가정하면 점수가 왜곡된다.
- **Shorts에는 보정 계수를 적용한다** (`β = 0.5`, 실데이터로 교정 예정). 조회수가 오르는
  속도가 자릿수 단위로 달라, 보정 없이는 모든 보드를 쇼츠가 뒤덮는다.

## 구조

```
GitHub Actions cron (하루 3회)
 └─ Python 파이프라인
     RSS 폴링(쿼터 0) → 스냅샷 배치 → 분류 → 점수 산출 → purge → 상황판 생성
          ↓
     Supabase (Postgres)
          ↓  읽기 전용, anon key + RLS
     Vercel (Next.js)
```

수집과 서빙이 완전히 분리돼 있다. 페이지를 여는 순간 유튜브 API를 부르지도, API 키에 닿지도
않는다 — 이미 계산돼 저장된 랭킹 캐시를 읽을 뿐이다. 따라서 트래픽이 늘어도 쿼터를 쓰지 않고,
키가 브라우저 번들로 갈 경로 자체가 없다.

전부 무료 티어 안에서 돈다. YouTube Data API(일 10,000유닛 — 98개 채널 한 주기가 약 9유닛),
GitHub Actions(공개 리포 무제한), Supabase(500MB, 30일 롤링 삭제로 관리), Vercel.

## 기술 스택

| 레이어 | 선택 |
|--------|------|
| 파이프라인 | Python 3.11, requests, PyYAML, supabase-py · pytest / ruff / mypy(strict) |
| DB | Supabase(Postgres), `ut_` 접두어 테이블, anon은 RLS 읽기 전용 |
| 웹 | Next.js 16(App Router), TypeScript, Tailwind CSS 4 · Vitest |
| 스케줄링 | GitHub Actions cron |

## 시작하기

```bash
git clone https://github.com/<owner>/utube-trend-tracer.git
cd utube-trend-tracer

# 1. 데이터베이스
#    Supabase SQL 편집기에서 db/schema.sql 실행 (멱등)

# 2. 시크릿
cp .env.example .env
#    YOUTUBE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY 입력

# 3. 파이프라인
python3 -m venv venv && source venv/bin/activate
pip install -r pipeline/requirements-dev.txt
cd pipeline
python -m scripts.sync_config      # 카테고리 → DB
python -m scripts.sync_seeds       # 시드 채널 → DB
python -m scripts.run_collect      # 수집 한 주기
python -m scripts.run_scoring      # 랭킹 산출

# 4. 웹
cd ../web
cp ../.env.example .env.local      # NEXT_PUBLIC_ anon 값만 남긴다
npm install && npm run dev
```

증가량을 재려면 스냅샷이 두 번 이상 필요하므로, 초기 몇 주기 동안은 보드가 빈다.
이 콜드스타트 상태는 숨기지 않고 안내 문구로 명시한다.

## 검증

```bash
# pipeline/
ruff check . && mypy app/ scripts/ && pytest tests/ -q

# web/
npm run lint && npm test && npm run build
```

## 운영

파이프라인은 매 주기 [docs/reports/status.md](docs/reports/status.md)에 상황판을 남긴다 —
시드 커버리지, RSS 통과율, 수집 신선도, 보관 정책 준수, 쿼터 사용량, 미분류율, 채널 상한 여유.
읽기 전용 산출물이며 웹에서 작업을 트리거하지 않는다. 트리거는 인증과 쓰기 엔드포인트를
요구하고, 그것은 새 보안 표면이기 때문이다. 조회에 실패한 항목은 조용히 통과시키지 않고
'조회 불가'로 표시하므로, DB 장애가 상황판을 함께 죽이지 않는다.

경고 상태별 대응 절차는 [docs/RUNBOOK.md](docs/RUNBOOK.md)에 있다.

## 약관 준수

- 수집한 데이터는 30일 롤링으로 삭제한다.
- 유튜브에서 삭제·비공개된 영상은 다음 주기에 이곳에서도 사라진다.
- 연령 제한 영상은 랭킹에서 제외한다.
- 재생은 항상 유튜브에서 이뤄지며, 이 사이트는 링크만 건다.
- 채널 소유자는 제외를 요청할 수 있다 — 연락처는 소개 페이지에 있고, 차단은 설정 파일만
  고치면 배포 없이 반영된다.

## 문서

명세주도개발(SDD) 순서대로 읽는다.

| 문서 | 내용 |
|------|------|
| [docs/SPEC.md](docs/SPEC.md) | 요구사항과 결정 기록 (D1~D14) |
| [docs/PLAN.md](docs/PLAN.md) | 아키텍처, 데이터 모델, 마일스톤 |
| [docs/DESIGN.md](docs/DESIGN.md) | IA, 와이어프레임, 디자인 토큰 |
| [docs/TASKS.md](docs/TASKS.md) | 진도율 대시보드와 태스크 |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | 운영 절차 |

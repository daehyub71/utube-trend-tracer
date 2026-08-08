# TASKS — utube-trend-tracer

> 기준: [SPEC.md](SPEC.md) v1.1 · [PLAN.md](PLAN.md) v1.0 — 체크 시마다 대시보드 갱신 (워크스페이스 규칙)

## 진도율 대시보드

| 마일스톤 | 게이지 | 진도 | 상태 |
|----------|--------|------|------|
| M0 셋업 | ██████████ | 100% (9/9) | ✅ 2026-08-08 |
| M1 분류·시드 | ██████████ | 100% (7/7) | ✅ 2026-08-08 |
| M2 수집 파이프라인 | █████████░ | 89% (8/9) | 🔄 cron 확인 대기 |
| M3 지수 산출 | ██████████ | 100% (5/5) | ✅ 2026-08-08 |
| M4 웹 프론트 | ██████████ | 100% (7/7) | ✅ 2026-08-08 |
| M5 admin·안전 | ░░░░░░░░░░ | 0% (0/4) | 🔜 |
| M6 교정·오픈 | ░░░░░░░░░░ | 0% (0/5) | 🔜 |
| **전체** | ███████░░░ | **75% (36/48)** | 🔄 |

---

## M0 셋업 ✅ (2026-08-08 완료)

완료 기준: pipeline 빈 실행 + web dev 실행 성공, Supabase에 ut_ 스키마 적용 확인, CI 뼈대 통과

- [x] 프로젝트 구조 생성 (config/, pipeline/app·tests, db/, .github/workflows) — 2026-08-08
- [x] 프로젝트 CLAUDE.md 작성 (스택·검증 명령·프로젝트 규칙) — 2026-08-08
- [x] .gitignore + .env.example (키 보호, NFR-3) — 2026-08-08
- [x] ut_ 스키마 마이그레이션 SQL 작성 (db/schema.sql, RLS 포함) — 2026-08-08
- [x] Supabase 인스턴스에 스키마 적용 + anon 읽기 정책 확인 — 2026-08-08 (7개 테이블·컬럼 일치, anon 읽기 6종 OK, anon 쓰기 401 차단 확인)
- [x] YouTube Data API 키 유효성 확인 — 2026-08-08 (videos.list·channels.list 실호출 성공, 2유닛 사용)
- [x] Python venv + requirements(-dev).txt 구성 — 2026-08-08 (ruff·mypy·pytest 3종 통과, app/config.py TDD 4 테스트)
- [x] Next.js 스캐폴드 (App Router·TS·Tailwind) + Vitest 설정 — 2026-08-08 (lint·test·build 3종 통과, Next 16.3 / React 19.2)
- [x] CI 뼈대 워크플로 (pipeline lint/test + web lint/test/build) — 2026-08-08 작성, 로컬에서 동일 명령 전부 통과.
      ⏸ 실제 Actions 실행 확인은 GitHub 리포 생성·푸시 후

## M1 분류·시드 ✅ (2026-08-08 완료)

완료 기준: 분류기 전 테스트 통과, 6개 카테고리 × 시드 10개 이상 등재, RSS 검증 통과 — **모두 충족**

- [x] categories.yaml 스키마 정의 + 초기 6카테고리(× 국내/해외) 키워드 작성 (D3, D9) — 12개 카테고리 전개, 해외 키워드 64개
- [x] (TDD) 카테고리 로더 + 검증 — 8 테스트 (중복·빈 키워드·불변성)
- [x] (TDD) 키워드 분류기 — 가중치(바이브코딩·AI 1.1)·미분류 플래그 (D10) — 15 테스트
- [x] (TDD) config → ut_categories DB 동기화 — 6 테스트, 실 DB 12행 반영 확인
- [x] seeds.yaml — 카테고리별 시드 발굴·등재 (D4) — **98개 채널** (카테고리당 13~17개), 쿼터 1,711유닛 사용
- [x] 시드 RSS 검증 스크립트 (실패 채널 리포트) — RSS 파서 8 테스트, 실검증 119/119 통과 후 휴면 21개 정리
- [x] blocklist.yaml 스키마 + 랭킹 제외 적용 로직 (FR-10, D12) — 9 테스트

**M1 검증 결과 (2026-08-08)**: ruff·mypy(strict, 12파일)·pytest(50 테스트) 전부 통과.
시드 채널 RSS 통과율 100%, 활성 채널 마지막 업로드 중앙값 1일 전.

## M2 수집 파이프라인 🔄 (cron 실행 확인만 대기)

완료 기준: Actions cron 3회 연속 자동 성공, 쿼터 로그 확인 — **가동 시점부터 콜드스타트 2주 시작**

- [x] (TDD) RSS 새 영상 감지 파서 (쿼터 0) — 8 테스트
- [x] (TDD) videos.list / channels.list 50개 배치 스냅샷 수집 — 15 테스트 (ISO 8601 길이 파싱 포함)
- [x] (TDD) 쿼터 트래커 + 예산 초과 시 수집 중단 (NFR-4, D14) — 8 테스트
- [x] (TDD) 30일 롤링 purge + 삭제·비공개 반영 (D12) — 10 테스트
- [x] (TDD) 졸업 로직 — 상한 2,000, 30일 무업로드·성과 하위 우선 (D11)
- [x] (TDD) 채널 카테고리 확정 — 영상 소재 분포 기반 (D9 이월 과제) — 7 테스트
- [x] search.list 발굴 — 일 예산제, 한국(한국어) 채널 필터 (D9, D14) — M1에서 완료
- [x] **로컬 수집 성공 (2026-08-08)** — 98채널·318영상 스냅샷, 쿼터 9유닛, 미분류율 13.8%
- [ ] GitHub Actions cron 가동 (하루 3회) ⏸ 워크플로 작성 완료, 실행 확인은 GitHub 리포 생성 후

## M3 지수 산출 ✅ (2026-08-08 완료)

완료 기준: 산식 규약 테스트 포함 전체 통과, 실데이터로 4개 보드 랭킹 생성 확인 — **모두 충족**

- [x] (TDD) 산식 규약 테스트 — `score ∝ 구독자^(1-α)` 관계 강제 (FR-7) — 9 테스트, α=0.7 실패 사례를 회귀 테스트로 보존
- [x] (TDD) velocity 산식 — α 0.25/1.0, floor 1,000, Δ시간 실측 — 11 테스트
- [x] (TDD) Shorts 판별(≤3분) + β 보정 (초기 0.5, D8)
- [x] (TDD) 결측 구간 보정 (NFR-7) — 구간 내 최이른·최신 스냅샷 사용
- [x] 4개 보드 ut_trend_scores 적재 + cron 통합 — 14 테스트, 실 DB 적재 확인

## M4 웹 프론트 ✅ (2026-08-08 완료)

완료 기준: DESIGN.md 합의 기록 존재, lint + vitest + build 3종 통과 — **모두 충족**

- [x] **DESIGN.md — IA·와이어프레임·UI 시안 → 사용자 합의** — 시안 v0.1 기본값으로 DQ1~DQ5 확정 (DESIGN v1.0)
- [x] Supabase anon key + RLS 읽기 전용 접속 설정 — `web/.env.local`, service key 미포함 확인
- [x] 홈 — 카테고리 선택(URL 쿼리 보존) + 4개 랭킹 보드 + 산출 기준 시각 표시
- [x] 채널 상세 — 30일 구독자·조회수 그래프(이중축 금지, 분리 배치), 소속 카테고리, 최근 영상 (D6)
- [x] 라이트/다크 모드 (NFR-6) — 토큰 3단 패턴(`:root`/`prefers-color-scheme`/`[data-theme]`), 시스템 기본
- [x] 정책 페이지 — 자체 지표 명시(NFR-2), 개인정보처리방침 + opt-out 연락처(D12), YouTube 출처(NFR-1)
- [x] lint + vitest(31 테스트) + build 통과

**M4 검증 결과 (2026-08-08)**: 개발 서버 실화면 확인 — 홈·정책·채널 상세 모두 HTTP 200,
점수 배지·Shorts 표시·유튜브 링크 렌더 확인. 콜드스타트 빈 보드는 "아직 집계 중" 안내로 표시되며
레이아웃이 유지된다 (DESIGN §5).

## M5 admin·안전 🔜

완료 기준: cron 후 리포트 자동 커밋 확인, 차단·연령제한 항목 랭킹 제외 검증

- [ ] admin 리포트 생성기 — 자동 점검(시드 공백·검증 노후·통과율·수집 중단 12h·보관 위반·랭킹 공백·쿼터 임박 + 미분류율·채널 상한 임박) (FR-9)
- [ ] 런북 문서화 — 카테고리 추가 → 시드 발굴 → 동기화 → 검증 → purge 순서
- [ ] blocklist·연령제한 제외 통합 테스트 (FR-10)
- [ ] cron 후 리포트 자동 커밋 — 민감정보 제외 (NFR-10, D13)

## M6 교정·오픈 🔜

완료 기준: 교정 기록 SPEC 반영, 보안 점검 게이트 통과, 공개 URL 동작

- [ ] 콜드스타트 2주 데이터 확보 확인 (스냅샷 연속성 점검)
- [ ] β(필요시 α) 교정 시연 → SPEC FR-7 갱신 (D8)
- [ ] 보안 점검 게이트 — security-review + 시크릿·CI 권한·아티팩트 점검 (NFR-5)
- [ ] README.md / README_KO.md 작성 + GitHub 푸쉬
- [ ] Vercel 배포 · 공개 오픈

---

## 트러블슈팅 기록

### 2026-08-08 · Mac Python SSL 인증서 검증 실패

- **증상**: 점검 스크립트에서 `ssl.SSLCertVerificationError: unable to get local issuer certificate` — Supabase·YouTube 양쪽 HTTPS 호출 모두 실패.
- **원인**: python.org 배포판 Python 3.13은 macOS 시스템 인증서를 쓰지 않고 자체 CA 번들을 요구한다 (Homebrew/시스템 Python과 다름).
- **해결**: `export SSL_CERT_FILE=$(python3 -c "import certifi; print(certifi.where())")` 로 실행.
  대안은 `/Applications/Python 3.13/Install Certificates.command` 1회 실행.
- **적용**: M0에서 venv 구성 시 `certifi`를 requirements에 포함하고, 파이프라인 진입점에서 `SSL_CERT_FILE` 미설정 시 certifi 경로를 자동 지정한다 (GitHub Actions Ubuntu 환경은 영향 없음).

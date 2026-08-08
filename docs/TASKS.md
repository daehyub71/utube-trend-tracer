# TASKS — utube-trend-tracer

> 기준: [SPEC.md](SPEC.md) v1.1 · [PLAN.md](PLAN.md) v1.0 — 체크 시마다 대시보드 갱신 (워크스페이스 규칙)

## 진도율 대시보드

| 마일스톤 | 게이지 | 진도 | 상태 |
|----------|--------|------|------|
| M0 셋업 | ██████████ | 100% (9/9) | ✅ 2026-08-08 |
| M1 분류·시드 | ░░░░░░░░░░ | 0% (0/6) | 🔜 |
| M2 수집 파이프라인 | ░░░░░░░░░░ | 0% (0/7) | 🔜 |
| M3 지수 산출 | ░░░░░░░░░░ | 0% (0/5) | 🔜 |
| M4 웹 프론트 | ░░░░░░░░░░ | 0% (0/7) | 🔜 |
| M5 admin·안전 | ░░░░░░░░░░ | 0% (0/4) | 🔜 |
| M6 교정·오픈 | ░░░░░░░░░░ | 0% (0/5) | 🔜 |
| **전체** | ██░░░░░░░░ | **21% (9/43)** | 🔄 |

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

## M1 분류·시드 🔜

완료 기준: 분류기 전 테스트 통과, 6개 카테고리 × 시드 10개 이상 등재, RSS 검증 통과

- [ ] categories.yaml 스키마 정의 + 초기 6카테고리(× 국내/해외) 키워드 작성 (D3, D9)
- [ ] (TDD) 키워드 분류기 — 가중치(바이브코딩·AI 1.1)·미분류 플래그 (D10)
- [ ] (TDD) config → ut_categories DB 동기화
- [ ] seeds.yaml — 카테고리별 수동 시드 10~20개 발굴·등재 (D4)
- [ ] 시드 RSS 검증 스크립트 (실패 채널 리포트)
- [ ] blocklist.yaml 스키마 + 랭킹 제외 적용 로직 (FR-10, D12)

## M2 수집 파이프라인 🔜

완료 기준: Actions cron 3회 연속 자동 성공, 쿼터 로그 확인 — **가동 시점부터 콜드스타트 2주 시작**

- [ ] (TDD) RSS 새 영상 감지 파서 (쿼터 0)
- [ ] (TDD) videos.list / channels.list 50개 배치 스냅샷 수집
- [ ] (TDD) 쿼터 트래커 + 예산 초과 시 수집 중단 (NFR-4, D14)
- [ ] (TDD) 30일 롤링 purge + 삭제·비공개 반영 (D12)
- [ ] (TDD) 졸업 로직 — 상한 2,000, 30일 무업로드·성과 하위 우선 (D11)
- [ ] search.list 발굴 — 일 예산제, 한국(한국어) 채널 필터 (D9, D14)
- [ ] GitHub Actions cron 가동 (하루 3회)

## M3 지수 산출 🔜

완료 기준: 산식 규약 테스트 포함 전체 통과, 실데이터로 4개 보드 랭킹 생성 확인

- [ ] (TDD) 산식 규약 테스트 — `score ∝ 구독자^(1-α)` 관계 강제 (FR-7)
- [ ] (TDD) velocity 산식 — α 0.25/1.0, floor 1,000, Δ시간 실측
- [ ] (TDD) Shorts 판별(≤3분) + β 보정 (초기 0.5, D8)
- [ ] (TDD) 결측 구간 보정 (NFR-7)
- [ ] 4개 보드 ut_trend_scores 적재 + cron 통합

## M4 웹 프론트 🔜

완료 기준: DESIGN.md 합의 기록 존재, lint + vitest + build 3종 통과

- [ ] **DESIGN.md — IA·와이어프레임·UI 시안 작성 → 사용자 합의** (구현 착수 게이트) 🔄 시안 v0.1 작성 완료(2026-08-08), DQ1~DQ5 사용자 검토 대기
- [ ] Supabase anon key + RLS 읽기 전용 접속 설정
- [ ] (TDD) 홈 — 카테고리 선택 + 4개 랭킹 보드 + 산출 기준 시각 표시
- [ ] (TDD) 채널 상세 — 30일 성장 그래프, 소속 카테고리, 급상승 영상 (D6)
- [ ] 라이트/다크 모드 (NFR-6)
- [ ] 정책 페이지 — 자체 지표 명시(NFR-2), 개인정보처리방침 + opt-out(D12), YouTube 브랜딩(NFR-1)
- [ ] lint + vitest + build 통과

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

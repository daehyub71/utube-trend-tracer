# CLAUDE.md — utube-trend-tracer

카테고리별 유튜브 트렌드 발견 서비스. 작업 전 `docs/SPEC.md` → `docs/PLAN.md` → `docs/TASKS.md` 순으로 읽는다 (워크스페이스 규칙).

## 스택·구조 (모노리포)

| 디렉토리 | 역할 | 스택 |
|----------|------|------|
| `pipeline/` | 수집·분류·지수 산출 (GitHub Actions cron 하루 3회) | Python 3.11+, venv, pytest |
| `web/` | 홈 4보드 + 채널 상세 + 정책 페이지 | Next.js App Router, TS, Tailwind, Vitest |
| `config/` | 코드 수정 없이 갱신하는 운영 데이터 | categories.yaml, seeds.yaml, blocklist.yaml |
| `db/` | Supabase 스키마 마이그레이션 SQL | Postgres |

## 프로젝트 고유 규칙

- **Supabase 테이블은 전부 `ut_` 접두어** — 다른 프로젝트와 인스턴스 공유 대비 (SPEC §6)
- **키 보호 (NFR-3)**: YouTube API 키·Supabase service key는 로컬 `.env`와 GitHub Actions Secrets에만. 웹은 anon key + RLS 읽기 전용, `ut_trend_scores` 중심 조회만
- **쿼터 (NFR-4)**: 일 10,000유닛 초과 금지 — search.list는 예산제 (초기 60회/일 → 정착 20회/일)
- **α ≥ 1.0 규약 (FR-7)**: "신규 뜨는" 보드의 α<1 금지 — 산식 규약 테스트가 강제한다. Shorts는 β 보정(초기 0.5, 콜드스타트 후 실데이터 교정 예정)
- 데이터는 30일 롤링 삭제 (YouTube 약관, NFR-1)
- 한국어 Windows 교차 작업: `PYTHONUTF8=1`, 파일 I/O에 `encoding="utf-8"` 명시

## 검증 (완료 선언 전 필수)

```bash
# pipeline/ 에서 (venv 활성화 후)
ruff check .
mypy app/
pytest tests/ -v

# web/ 에서
npm run lint
npm test
npm run build
```

## 실행

```bash
# 수집 파이프라인 로컬 1회 실행 (harness 모드)
cd pipeline && python -m app.collect   # (M2에서 확정)

# 웹 개발 서버
cd web && npm run dev
```

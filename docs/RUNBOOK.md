# RUNBOOK — utube-trend-tracer 운영 절차

현재 상태는 [운영 상황판](reports/status.md)에서 확인한다 (수집 cron이 돌 때마다 자동 갱신).
상황판은 **읽기 전용 산출물**이며 (SPEC FR-9), 조치는 여기 적힌 명령으로 실행한다.

모든 명령은 `pipeline/` 에서 가상환경을 활성화한 뒤 실행한다.

```bash
cd pipeline
source ../venv/bin/activate    # Windows: ..\venv\Scripts\activate
```

---

## 상황판 항목별 대응

| 항목 | 상태가 나쁠 때 | 명령 |
|------|---------------|------|
| 시드 커버리지 | 시드 0개 또는 10개 미만 카테고리 | `python -m scripts.discover_seeds --only <대분류>` → `python -m scripts.sync_seeds` |
| RSS 통과율 | 90% 미만 | `python -m scripts.verify_seeds --prune` (실패·휴면 채널 정리) |
| RSS 검증 기록 | 7일 초과 | `python -m scripts.verify_seeds --json ../docs/reports/rss_verify.json` |
| 수집 신선도 | 12시간 초과 | GitHub Actions → Collect 워크플로 로그 확인 → `workflow_dispatch` 로 수동 실행 |
| 보관 정책 | 30일 초과 데이터 존재 | `python -m scripts.run_collect` (purge가 수집 주기에 포함되어 있다) |
| 랭킹 커버리지 | 랭킹 0건 | 콜드스타트면 정상. 아니면 `python -m scripts.run_scoring --dry-run` 으로 산출 대상 수 확인 |
| 쿼터 사용량 | 80% 초과 | 발굴(`discover_seeds`)을 멈춘다. 소진되면 다음 날 자동 복구 — 수집만 멈추고 서빙은 정상 |
| 미분류율 | 30% 초과 | `config/categories.yaml` 에 키워드 보강 → `python -m scripts.sync_config`. 2주 지속되면 LLM 분류 도입 검토 (D10) |
| 추적 채널 수 | 상한(2,000) 근접 | 졸업이 동작 중인지 확인. 신규 편입은 졸업과 교환된다 (D11) |

---

## 절차 1 — 카테고리 추가

카테고리는 **코드 수정 없이 YAML만 고쳐** 추가한다 (SPEC FR-1, 확장형 체계).

1. `config/categories.yaml` 의 `parents:` 에 항목 추가 (id·name·weight·keywords)
2. 검증: `python -m scripts.sync_config --dry-run` — 전개된 카테고리 목록을 확인
3. DB 반영: `python -m scripts.sync_config`
4. 시드 발굴: `pipeline/scripts/discover_seeds.py` 의 `SEARCH_QUERIES` 에 검색어를 추가한 뒤
   `python -m scripts.discover_seeds --only <새 대분류>`
5. RSS 검증·정리: `python -m scripts.verify_seeds --prune`
6. DB 등재: `python -m scripts.sync_seeds`
7. 상황판 갱신: `python -m scripts.build_report`

> 쿼터 주의: `discover_seeds` 는 검색어 1개당 100유닛이다. `--dry-run` 으로 예상치를 먼저 본다.

## 절차 2 — 채널 제외 요청(opt-out) 처리

채널 소유자의 요청은 **설정 파일만 고쳐** 즉시 반영한다 (FR-10, D12). 배포가 필요 없다.

1. `config/blocklist.yaml` 의 `channels:` 에 추가 — **사유와 날짜를 반드시 남긴다**

   ```yaml
   channels:
     - id: UCxxxxxxxxxxxxxxxxxxxxxx
       reason: 소유자 opt-out 요청 (2026-08-08)
   ```

2. 다음 수집 주기부터 수집·랭킹에서 빠진다. 즉시 반영하려면 `python -m scripts.run_scoring`
3. 요청자에게 처리 완료를 회신한다

부적절한 콘텐츠 신고도 같은 절차로 `videos:` 에 등재한다.

## 절차 3 — 수집이 멈췄을 때

1. 상황판의 **수집 신선도**와 **쿼터 사용량**을 먼저 본다
2. 쿼터 소진이면 조치 불필요 — 다음 날 자동 복구된다 (서빙은 정상 동작)
3. 쿼터가 남았는데 멈췄다면 GitHub Actions → Collect 워크플로 로그 확인
4. Secrets 만료·오류가 의심되면 `python -m db/check_youtube.py`, `python db/check_schema.py` 로 연결 점검
5. 복구 후 수동 실행: Actions에서 `Run workflow`, 또는 로컬에서 `python -m scripts.run_collect`

> 수집이 한두 주기 빠져도 랭킹은 직전 값으로 서빙된다 (NFR-7). 급하게 되돌릴 필요 없다.

## 절차 4 — 정기 점검 (주 1회 권장)

```bash
python -m scripts.verify_seeds --prune --json ../docs/reports/rss_verify.json
python -m scripts.sync_seeds
python -m scripts.build_report
```

상황판의 **다음 조치** 항목이 비어 있으면 정상이다.

---

## 검증 (코드 변경 후 필수)

```bash
# pipeline/
ruff check . && mypy app/ scripts/ && pytest tests/ -q

# web/
npm run lint && npm test && npm run build
```

## 배포 전 보안 점검 (필수)

프로덕션 반영·CI 활성화·외부 공개 전에는 반드시 수행한다 (워크스페이스 규칙).

1. 보안 리뷰 실행 — 변경분의 취약점 검토
2. 시크릿 점검 — `git log -p | grep -iE "api[_-]?key|secret|eyJ"` 로 커밋 이력 확인
3. CI 권한 점검 — 워크플로 `permissions` 최소화, Secrets 사용 확인
4. 산출물 점검 — `docs/reports/` 에 키·연락처가 없는지 확인 (NFR-10, D13)

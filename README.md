# utube-trend-tracer

> [한국어 README](README_KO.md)

Category-based YouTube trend discovery for Korean viewers and creators.

YouTube retired its official Trending page in July 2025. There is no API that returns
"what's rising in food right now," so this service computes that signal itself from
periodic snapshots of channel and video statistics.

## What it does

Pick a category (food, travel, IT, AI/coding, vlog, fitness — each split into domestic
and overseas subject matter) and see four rankings:

| Board | Measures | Purpose |
|-------|----------|---------|
| Trending videos | View velocity, uploaded within 7 days | What's rising right now |
| Rising videos | View velocity relative to subscriber count | A small channel's breakout video |
| Trending channels | Weekly view growth | Channels gaining momentum |
| Rising channels | Subscriber growth, under 100k subs | Newcomers worth watching |

Every ranking is labeled as a self-computed metric, not a YouTube official one.

## How the score works

```
score = Δvalue / (Δhours × max(subscribers, 1000)^α)
```

The exponent `α` is what separates the two kinds of board:

- **Trending** uses `α = 0.25`, so absolute scale still counts but only as a mild handicap.
- **Rising** uses `α = 1.0`, which makes the score scale-neutral — a channel with 8k
  subscribers and one with 800k are judged on the same footing.

**`α ≥ 1.0` for rising boards is a hard rule, enforced by tests.** When Δ is proportional
to subscriber count, `score ∝ subscribers^(1-α)`; any `α < 1` quietly turns "rising" back
into a size ranking. An early demo with `α = 0.7` did exactly that, and that failure is
kept as a regression test.

Two more details matter in practice:

- **Δhours comes from actual snapshot timestamps**, never the scheduled cron time.
  GitHub Actions can run tens of minutes late, and assuming the schedule would distort scores.
- **Shorts get a correction factor** (`β = 0.5`, to be calibrated on real data). Their view
  velocity is an order of magnitude different, so without it they take over every board.

## Architecture

```
GitHub Actions cron (3×/day)
 └─ Python pipeline
     RSS poll (0 quota) → snapshot batches → classify → score → purge → ops report
          ↓
     Supabase (Postgres)
          ↓  read-only, anon key + RLS
     Vercel (Next.js)
```

Collection and serving are fully separated. A page view never calls the YouTube API and
never touches the API key — it reads an already-computed ranking cache. Traffic therefore
costs no quota, and the key has no path into the browser bundle.

Everything runs inside free tiers: YouTube Data API (10,000 units/day; a full cycle over
98 channels costs about 9), GitHub Actions (unlimited on public repos), Supabase (500MB,
managed by 30-day rolling deletion), and Vercel.

## Tech stack

| Layer | Choice |
|-------|--------|
| Pipeline | Python 3.11, requests, PyYAML, supabase-py · pytest / ruff / mypy (strict) |
| Database | Supabase (Postgres), tables prefixed `ut_`, RLS read-only for anon |
| Web | Next.js 16 (App Router), TypeScript, Tailwind CSS 4 · Vitest |
| Scheduling | GitHub Actions cron |

## Getting started

```bash
git clone https://github.com/<owner>/utube-trend-tracer.git
cd utube-trend-tracer

# 1. Database
#    Run db/schema.sql in the Supabase SQL editor (idempotent).

# 2. Secrets
cp .env.example .env
#    Fill YOUTUBE_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY.

# 3. Pipeline
python3 -m venv venv && source venv/bin/activate
pip install -r pipeline/requirements-dev.txt
cd pipeline
python -m scripts.sync_config      # categories → DB
python -m scripts.sync_seeds       # seed channels → DB
python -m scripts.run_collect      # one collection cycle
python -m scripts.run_scoring      # compute rankings

# 4. Web
cd ../web
cp ../.env.example .env.local      # keep only the NEXT_PUBLIC_ anon values
npm install && npm run dev
```

Rankings need at least two snapshots to measure growth, so boards stay empty during the
first cycles. That cold-start state is rendered explicitly rather than hidden.

## Verification

```bash
# pipeline/
ruff check . && mypy app/ scripts/ && pytest tests/ -q

# web/
npm run lint && npm test && npm run build
```

## Operations

The pipeline writes a status dashboard to [docs/reports/status.md](docs/reports/status.md)
on every run — seed coverage, RSS pass rate, collection freshness, retention compliance,
quota usage, unclassified rate, and channel-limit headroom. It is a read-only artifact:
the web app never triggers work, which keeps the console from becoming a new attack surface.
Each check that cannot be read is marked "unavailable" instead of silently passing, so a
database outage does not take the dashboard down with it.

Procedures for every warning state are in [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Terms compliance

- Data is deleted after 30 days on a rolling basis.
- Videos removed or made private on YouTube disappear here on the next cycle.
- Age-restricted videos are excluded from rankings.
- Playback always happens on YouTube; this site links out.
- Channel owners can request removal — the contact address is on the About page, and
  blocking takes effect by editing a config file, without a deploy.

## Documentation

Specification-driven, in reading order:

| Document | Contents |
|----------|----------|
| [docs/SPEC.md](docs/SPEC.md) | Requirements and decision log (D1–D14) |
| [docs/PLAN.md](docs/PLAN.md) | Architecture, data model, milestones |
| [docs/DESIGN.md](docs/DESIGN.md) | IA, wireframes, design tokens |
| [docs/TASKS.md](docs/TASKS.md) | Progress dashboard and task breakdown |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Operational procedures |

# WordVoyage

WordVoyage is a production-oriented Bluesky bot that posts a daily "beautiful or untranslatable word" with:
- meaning
- etymology
- usage example
- a clean image card

## Recommended Stack

Use **plain Python** for v1.

Why:
- Lower complexity, faster shipping.
- Your workload is scheduled jobs, not a public API server.
- Easier ops for GitHub Actions + Postgres.

Use FastAPI later only if you need:
- admin dashboard API
- manual trigger endpoints
- moderation/review workflows

Django is not recommended for v1 because it is heavier than needed.

## Project Structure

```text
wordVoyage/
├── .github/
│   └── workflows/
│       └── wordvoyage.yml
├── docs/
│   └── architecture.md
├── sql/
│   └── schema.sql
├── src/
│   └── wordvoyage/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── scheduler.py
│       ├── generate/
│       │   └── claude_writer.py
│       ├── render/
│       │   └── card_renderer.py
│       ├── publish/
│       │   └── bluesky_client.py
│       ├── storage/
│       │   ├── db.py
│       │   └── repositories.py
│       └── jobs/
│           ├── main_reveal.py
│           ├── deep_dive.py
│           └── quiz.py
└── tests/
    ├── test_scheduler.py
    └── test_validation.py
```

## Data Layer

PostgreSQL schema is in [sql/schema.sql](/Users/vignesh/dev/ai-projects/wordVoyage/sql/schema.sql).

## Job Flow Diagram

Architecture and flow diagram are in [docs/architecture.md](/Users/vignesh/dev/ai-projects/wordVoyage/docs/architecture.md).

## Local Dry-Run

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -e .`.
3. Copy `.env.example` to `.env`.
4. Set `DRY_RUN=true`, `POSTING_ENABLED=false`, and `FORCE_SLOT=main_reveal`.
   - Optional: set `CARD_THEME=auto|orbital|sunset|minimal`
   - `ALLOW_CURATED_FALLBACK=false` keeps generation Claude-first strict.
   - `DEEP_DIVE_WITH_IMAGE=false` and `QUIZ_WITH_IMAGE=false` post text-only replies.
   - Set `DATABASE_URL` to enable DB-backed no-repeat enforcement.
5. Run `python -m wordvoyage.main`.

## No-Repeat Enforcement

- `main_reveal` now loads previously used words from Postgres.
- It asks Claude to avoid those words.
- Before live posting, it claims `(word, language)` in `words` table via unique constraint.
- If duplicate is detected, it regenerates automatically.

Output artifacts are written to `artifacts/<YYYY-MM-DD>/main_reveal/`:
- rendered card image (`.png`)
- intended post log (`intended_post_main_reveal.json`)

Thread state is tracked at `artifacts/<YYYY-MM-DD>/thread_state.json`:
- `main_reveal` is stored as thread root
- `deep_dive` and `quiz` automatically reply to that root URI/CID

-- WordVoyage PostgreSQL schema (v1)
-- Timezone convention:
-- - Store all timestamps as timestamptz in UTC
-- - Business scheduling evaluated in America/New_York inside app code

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'post_slot') THEN
    CREATE TYPE post_slot AS ENUM ('main_reveal', 'deep_dive', 'quiz');
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'post_status') THEN
    CREATE TYPE post_status AS ENUM ('planned', 'generating', 'ready', 'posting', 'posted', 'failed', 'skipped');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS words (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  word TEXT NOT NULL,
  language_name TEXT NOT NULL,
  script_form TEXT,
  transliteration TEXT,
  pronunciation_guide TEXT,
  meaning TEXT NOT NULL,
  etymology TEXT NOT NULL,
  usage_example TEXT NOT NULL,
  usage_example_translation TEXT,
  source_notes TEXT,
  is_untranslatable BOOLEAN NOT NULL DEFAULT FALSE,
  quality_score NUMERIC(5,2) NOT NULL DEFAULT 0.00,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (word, language_name)
);

CREATE TABLE IF NOT EXISTS generation_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_date DATE NOT NULL,
  slot post_slot NOT NULL,
  prompt_version TEXT NOT NULL,
  model_name TEXT NOT NULL,
  raw_request JSONB NOT NULL,
  raw_response JSONB,
  validation_errors JSONB,
  status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (run_date, slot)
);

CREATE TABLE IF NOT EXISTS daily_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_date DATE NOT NULL,
  slot post_slot NOT NULL,
  word_id UUID REFERENCES words(id) ON DELETE RESTRICT,
  generation_run_id UUID REFERENCES generation_runs(id) ON DELETE SET NULL,
  parent_post_id UUID REFERENCES daily_posts(id) ON DELETE SET NULL,
  caption_text TEXT NOT NULL,
  alt_text TEXT NOT NULL,
  image_local_path TEXT,
  idempotency_key TEXT NOT NULL,
  status post_status NOT NULL DEFAULT 'planned',
  scheduled_for TIMESTAMPTZ,
  posted_at TIMESTAMPTZ,
  bluesky_uri TEXT,
  bluesky_cid TEXT,
  failure_reason TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (post_date, slot),
  UNIQUE (idempotency_key)
);

CREATE TABLE IF NOT EXISTS engagement_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  daily_post_id UUID NOT NULL REFERENCES daily_posts(id) ON DELETE CASCADE,
  likes INTEGER NOT NULL DEFAULT 0 CHECK (likes >= 0),
  reposts INTEGER NOT NULL DEFAULT 0 CHECK (reposts >= 0),
  replies INTEGER NOT NULL DEFAULT 0 CHECK (replies >= 0),
  quotes INTEGER NOT NULL DEFAULT 0 CHECK (quotes >= 0),
  bookmarks INTEGER CHECK (bookmarks IS NULL OR bookmarks >= 0),
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_words_language_created_at
  ON words (language_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_daily_posts_status_sched
  ON daily_posts (status, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_daily_posts_posted_at
  ON daily_posts (posted_at DESC);

CREATE INDEX IF NOT EXISTS idx_engagement_daily_post_captured
  ON engagement_snapshots (daily_post_id, captured_at DESC);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_daily_posts_updated_at ON daily_posts;
CREATE TRIGGER trg_daily_posts_updated_at
BEFORE UPDATE ON daily_posts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

COMMIT;


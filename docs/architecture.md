# WordVoyage Architecture (v1)

## Why Plain Python

Plain Python is the best default for v1 because WordVoyage is a scheduler-driven pipeline (not an always-on API product yet).

- Keep deploy surface small.
- Keep maintenance simple.
- Maximize shipping speed and reliability.

Add FastAPI only when you need external triggers or an operator dashboard.

## Runtime Flow

```mermaid
flowchart TD
  A[GitHub Actions Cron<br/>every 30 min UTC] --> B[entrypoint: python -m wordvoyage.main]
  B --> C{Is now in ET slot window?}
  C -- No --> Z[Exit 0]
  C -- Yes --> D[Load DB state for post_date+slot]
  D --> E{Already posted?}
  E -- Yes --> Z
  E -- No --> F[Select candidate word<br/>with dedupe rules]
  F --> G[Claude generation<br/>meaning + etymology + example]
  G --> H[Validate schema + quality + safety]
  H --> I[Render card image + alt text]
  I --> J[Create/Upsert daily_posts row<br/>status=ready]
  J --> K[Publish to Bluesky]
  K --> L{Publish success?}
  L -- Yes --> M[Update row: status=posted<br/>save uri/cid/posted_at]
  L -- No --> N[Update row: status=failed<br/>retry_count+1 + reason]
  M --> O[Snapshot engagement later]
  N --> O
```

## Daily Slot Strategy (America/New_York)

- `main_reveal`: 1:00 PM to 2:00 PM ET
- `deep_dive`: 6:00 PM to 7:00 PM ET
- `quiz`: optional evening slot (for example 9:00 PM ET)

Important: evaluate with `America/New_York` timezone, not fixed EST, to handle DST automatically.

## Idempotency and Reliability

- One row per `post_date + slot` in `daily_posts`.
- `idempotency_key` blocks duplicate posts on retries.
- Safe reruns from GitHub Actions are expected behavior.
- If a run fails, keep `failed` state and retry in next scheduler tick.

## Data Design Notes

- `words` is reusable content inventory and dedupe anchor.
- `generation_runs` stores prompt/model/raw I/O for debugging and quality tuning.
- `daily_posts` is operational truth (planned -> posted or failed).
- `engagement_snapshots` captures growth over time for viral analysis.


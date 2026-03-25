from __future__ import annotations

def connect(database_url: str):
    try:
        import psycopg
    except Exception as exc:
        raise RuntimeError(
            "psycopg is required for DATABASE_URL usage. Install dependencies with `pip install -e .`."
        ) from exc
    return psycopg.connect(database_url)

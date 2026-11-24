"""PostgreSQL access (psycopg pool) and schema. Every table carries user_id."""
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

pool = ConnectionPool(
    settings.database_url, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=False
)

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS contracts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  filename text NOT NULL,
  size_bytes bigint NOT NULL,
  status text NOT NULL DEFAULT 'processing' CHECK (status IN ('processing','reviewed','failed')),
  error text,
  page_count int,
  full_text text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contracts_user_idx ON contracts (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chunks (
  id bigserial PRIMARY KEY,
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  user_id text NOT NULL,
  idx int NOT NULL,
  section_label text,
  page_start int,
  page_end int,
  char_start int NOT NULL,
  char_end int NOT NULL,
  text text NOT NULL,
  embedding halfvec({settings.embed_dim}),
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_contract_idx ON chunks (contract_id, user_id);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);

CREATE TABLE IF NOT EXISTS reviews (
  id bigserial PRIMARY KEY,
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  user_id text NOT NULL,
  item_key text NOT NULL,
  status text NOT NULL CHECK (status IN ('found','not found','unclear')),
  summary text NOT NULL,
  chunk_id bigint REFERENCES chunks(id) ON DELETE SET NULL,
  quote text,
  section_label text,
  page_start int,
  UNIQUE (contract_id, item_key)
);

CREATE TABLE IF NOT EXISTS messages (
  id bigserial PRIMARY KEY,
  contract_id uuid NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  user_id text NOT NULL,
  role text NOT NULL CHECK (role IN ('user','assistant')),
  content text NOT NULL,
  citations jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_contract_idx ON messages (contract_id, user_id, id);
"""
# Note: no ANN index on `embedding` on purpose. pgvector's HNSW/IVFFlat on `vector`
# stop at 2,000 dims, and every search is already filtered to a single contract
# (tens of chunks), where an exact scan is fast and always returns full results.


def init_db() -> None:
    pool.open()
    pool.wait(timeout=30)
    with pool.connection() as conn:
        conn.execute(SCHEMA)


def fetch(sql: str, params=(), one: bool = False):
    with pool.connection() as conn:
        cur = conn.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
    if one:
        return rows[0] if rows else None
    return rows


def many(sql: str, seq) -> None:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, seq)

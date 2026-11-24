"""Background processing: extract -> chunk -> embed -> review. Runs in a worker thread."""
import logging

from . import db
from .chunking import chunk_text
from .extract import ExtractionError, build_text, extract_pages
from .llm import RATE_MSG, LLMError, RateLimited, embed
from .retrieval import vec_literal
from .review import run_review

log = logging.getLogger("pipeline")


def _set_status(contract_id, user_id: str, status: str, error: str | None = None) -> None:
    db.fetch("UPDATE contracts SET status=%s, error=%s WHERE id=%s AND user_id=%s",
             (status, error, contract_id, user_id))


def embed_missing(contract_id, user_id: str) -> None:
    rows = db.fetch("SELECT id, section_label, text FROM chunks WHERE contract_id=%s AND user_id=%s "
                    "AND embedding IS NULL ORDER BY idx", (contract_id, user_id))
    if not rows:
        return
    vectors = embed([f"{r['section_label']}\n{r['text']}" for r in rows])
    db.many("UPDATE chunks SET embedding=%s::halfvec WHERE id=%s AND user_id=%s",
            [(vec_literal(v), r["id"], user_id) for v, r in zip(vectors, rows)])


def run_pipeline(contract_id, user_id: str, filename: str, raw: bytes | None) -> None:
    try:
        if raw is not None:
            pages = extract_pages(filename, raw)
            full, spans = build_text(pages)
            chunks = chunk_text(full, spans)
            if not chunks:
                raise ExtractionError("No readable text found in the file.")
            db.fetch("UPDATE contracts SET full_text=%s, page_count=%s WHERE id=%s AND user_id=%s",
                     (full, sum(1 for n, _ in pages if n), contract_id, user_id))
            db.fetch("DELETE FROM chunks WHERE contract_id=%s AND user_id=%s", (contract_id, user_id))
            db.many(
                "INSERT INTO chunks (contract_id, user_id, idx, section_label, page_start, page_end, char_start, char_end, text) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(contract_id, user_id, c["idx"], c["section_label"], c["page_start"], c["page_end"],
                  c["char_start"], c["char_end"], c["text"]) for c in chunks])
        elif not db.fetch("SELECT 1 FROM chunks WHERE contract_id=%s AND user_id=%s LIMIT 1",
                          (contract_id, user_id), one=True):
            raise ExtractionError("The original file was not kept. Delete this contract and upload it again.")
        try:
            embed_missing(contract_id, user_id)
        except RateLimited:
            raise
        except LLMError as e:  # keep going with keyword-only retrieval
            log.warning("embedding failed for %s: %s", contract_id, e)
        run_review(contract_id, user_id)
        _set_status(contract_id, user_id, "reviewed")
    except RateLimited:
        _set_status(contract_id, user_id, "failed", RATE_MSG + " Press Retry.")
    except ExtractionError as e:
        _set_status(contract_id, user_id, "failed", str(e))
    except Exception:
        log.exception("pipeline failed for %s", contract_id)
        _set_status(contract_id, user_id, "failed", "Something went wrong while processing this contract. Press Retry.")

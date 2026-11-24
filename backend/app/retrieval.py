"""Hybrid retrieval: pgvector cosine search + Postgres full-text search, merged with
reciprocal rank fusion. Every query is filtered by contract_id AND user_id."""
import re

from . import db

RRF_K = 60
POOL = 12
STOP = set("what which does this that with from have about there their would should could when where "
           "contract agreement please tell show says into under than then they them your".split())


def vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def question_terms(text: str) -> list[str]:
    return list(dict.fromkeys(w for w in re.findall(r"[a-zA-Z]{4,}", text.lower()) if w not in STOP))


def hybrid(contract_id, user_id: str, qvec: list[float] | None, terms: list[str],
           k: int = 6, include_first: bool = False) -> list[dict]:
    semantic: list[int] = []
    if qvec:
        semantic = [r["id"] for r in db.fetch(
            "SELECT id FROM chunks WHERE contract_id=%s AND user_id=%s AND embedding IS NOT NULL "
            "ORDER BY embedding <=> %s::halfvec LIMIT %s", (contract_id, user_id, vec_literal(qvec), POOL))]
    keyword: list[int] = []
    clean = [t for t in (re.sub(r"\W", "", t) for t in terms) if t]
    if include_first:  # parties / start date normally sit in the preamble
        first = db.fetch("SELECT id FROM chunks WHERE contract_id=%s AND user_id=%s AND idx=0",
                         (contract_id, user_id), one=True)
        if first:
            keyword.append(first["id"])
    if clean:
        q = " | ".join(clean)
        keyword += [r["id"] for r in db.fetch(
            "SELECT id FROM chunks WHERE contract_id=%s AND user_id=%s AND tsv @@ to_tsquery('english', %s) "
            "ORDER BY ts_rank(tsv, to_tsquery('english', %s)) DESC LIMIT %s",
            (contract_id, user_id, q, q, POOL))]
    score: dict[int, float] = {}
    for ranking in (semantic, keyword):
        for rank, cid in enumerate(ranking):
            score[cid] = score.get(cid, 0) + 1 / (RRF_K + rank + 1)
    top = sorted(score, key=score.get, reverse=True)[:k]
    if not top:
        return []
    rows = db.fetch(
        "SELECT id, idx, section_label, page_start, page_end, char_start, char_end, text FROM chunks "
        "WHERE contract_id=%s AND user_id=%s AND id = ANY(%s)", (contract_id, user_id, top))
    by_id = {r["id"]: r for r in rows}
    return [by_id[i] for i in top if i in by_id]

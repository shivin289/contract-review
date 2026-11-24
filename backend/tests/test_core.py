from fastapi.testclient import TestClient

from app.chunking import chunk_text
from app.extract import build_text
from app.main import app
from app.quotes import citations_from_answer, normalize, quote_in
from app.review import finalize, parse_json

TEXT = """SERVICE AGREEMENT

This Agreement is made between Acme Ltd and Beta Inc.

1. Term
The term is twelve (12) months from 1 January 2026.

""" + "Filler sentence about nothing. " * 15 + """

5. Termination
5.1 Either party may terminate this Agreement with thirty (30) days\u2019 written notice.
"""


def test_quote_normalisation():
    assert quote_in("terminate this Agreement with thirty (30) days' written notice", TEXT)
    assert quote_in("with  thirty (30) days\u2019\nwritten notice", TEXT)
    assert not quote_in("either party may terminate immediately", TEXT)
    assert not quote_in("terminate ... written notice", TEXT)


def test_chunks_keep_clauses_pages_offsets():
    pages = [(1, TEXT[:200]), (2, TEXT[200:])]
    full, spans = build_text(pages)
    chunks = chunk_text(full, spans)
    assert any("Termination" in (c["section_label"] or "") for c in chunks)
    for c in chunks:
        assert full[c["char_start"]:c["char_end"]] == c["text"]
        assert c["page_start"] in (1, 2)


def test_finalize_downgrades_fake_quotes():
    chunks = [dict(id=1, text="Either party may terminate on 30 days written notice.", section_label="5",
                   page_start=2, char_start=0, char_end=50)]
    full = chunks[0]["text"]
    ok = finalize(dict(status="found", summary="x", chunk_id=1, quote="may terminate on 30 days written notice"), chunks, full)
    assert ok["status"] == "found" and ok["chunk"]["id"] == 1
    fake = finalize(dict(status="found", summary="x", chunk_id=1, quote="may terminate on 90 days written notice"), chunks, full)
    assert fake["status"] == "unclear" and fake["quote"] is None
    nf = finalize(dict(status="not_found", summary="", chunk_id=None, quote=None), chunks, full)
    assert nf["status"] == "not found"


def test_parse_json_handles_fences():
    assert parse_json('```json\n{"status": "found"}\n```') == {"status": "found"}
    assert parse_json("no json here") is None


def test_chat_citations_flag_unverified():
    chunks = [dict(id=3, text="Governed by the laws of Delaware.", section_label="9", page_start=4,
                   char_start=0, char_end=30)]
    cites = citations_from_answer('Yes: "Governed by the laws of Delaware." and "Governed by French law."', chunks)
    assert [c["verified"] for c in cites] == [True, False]


def test_api_requires_valid_token():
    client = TestClient(app)  # lifespan (DB) not started
    assert client.get("/api/contracts").status_code == 401
    assert client.get("/api/contracts", headers={"Authorization": "Bearer garbage"}).status_code == 401
    assert client.delete("/api/contracts/3f2b6c1e-0000-4000-8000-000000000000").status_code == 401

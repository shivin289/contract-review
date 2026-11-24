# Contract Review Assistant

Upload a contract (PDF, DOCX, TXT), and the app checks it against a fixed checklist. Every finding is quoted word for word from the contract, with its page or section. Findings come only from the contract text.

## 1. Project overview
A signed-in user uploads a contract. A background job extracts the text, splits it into clauses, embeds them, and reviews eight checklist items: parties, start date and term, payment terms, termination, limitation of liability, confidentiality, governing law, auto-renewal. The user can then chat with the contract; answers are grounded in it and stream live.

## 2. Problem statement
LLMs invent clauses. The app treats the model as untrusted: it may only choose from retrieved excerpts, and the backend rejects any quote that is not literally in the contract.

## 3. Key features
Clerk auth · per-user data isolation · upload with 20 MB limit and status tracking · clause-aware chunking with page/section metadata · hybrid retrieval (pgvector + full-text) · verified quotes · "Show in contract" highlighting · streaming chat with verified citations · persistent review and chat history · retry on failure · eval script.

## 4. Technology stack
| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Clerk | First-class Clerk components, simple SPA-style pages |
| Backend | FastAPI (Python) | Best PDF/DOCX tooling (PyMuPDF, python-docx), easy SSE and background tasks |
| Database | PostgreSQL 16 + pgvector | One store for contracts, reviews, chat, vectors and full-text |
| Auth | Clerk, JWT verified in backend via JWKS | Required by the brief |
| AI | OpenRouter free models (chat + embeddings) | Suggested; OpenAI-compatible API |

## 5. System architecture
```
Browser (Next.js + Clerk) --Bearer JWT--> FastAPI --> PostgreSQL (+pgvector)
                                            |  background thread: extract -> chunk -> embed -> review
                                            +--> OpenRouter (embeddings, chat, streaming chat)
```

## 6. Application workflow
1. Upload -> `202` with status `processing`. 2. Worker extracts, chunks, stores chunks, embeds them in batches. 3. For each checklist item: retrieve, ask the model, verify the quote, store. 4. Status becomes `reviewed` (or `failed` with a readable error and a Retry button). The UI polls and shows progress.

## 7. Database design
`contracts` (status, full_text) · `chunks` (section_label, page_start/end, char offsets, `halfvec(2048)` embedding, generated `tsvector`) · `reviews` (one row per item, status, summary, quote, chunk_id) · `messages` (role, content, citations jsonb). Every table has `user_id`. Schema is created at startup (`backend/app/db.py`).

No vector index: pgvector's HNSW/IVFFlat on `vector` stop at 2,000 dimensions (the suggested model has 2,048), and each search is already filtered to one contract, where an exact scan is fast and always returns complete results.

## 8. Authentication and authorization
The backend verifies the Clerk session token on every request (`app/auth.py`): RS256 signature via Clerk's JWKS, `exp`, issuer, and `azp` against `CLERK_AUTHORIZED_PARTIES`. The user id is taken only from the verified `sub` claim. The JWKS URL and issuer are derived from the publishable key.

## 9. Document processing
PDF text is extracted per page (PyMuPDF), DOCX by paragraphs and tables (python-docx), TXT as UTF-8 (form feeds count as pages). Whitespace is normalized. Files are sniffed by their first bytes, not just extension. Scanned PDFs with no text become `failed` with a clear message. Processing runs in a background thread, so uploads never block the server.

## 10. Chunking strategy
Split at numbered clauses (`5.`, `5.1`), `Article/Section/Clause N`, and ALL-CAPS headings. Tiny segments (<300 chars) stay attached to the next body so headings are not orphaned; long clauses (>2,200 chars) are split at line or sentence ends and labelled "(cont.)". Each chunk stores its section label, page range and character offsets into the full text. DOCX/TXT have no reliable pages, so only the section is shown.

## 11. Embedding strategy
Chunks are embedded as `section label + text` in batches of 32 (one request per batch, not per chunk), stored as `halfvec(2048)`. The eight checklist queries are embedded in a single batched call. If embeddings fail (not rate limits), retrieval falls back to keyword search so the review still works.

## 12. Retrieval strategy
Per item: top 12 by cosine similarity plus top 12 by full-text search using item-specific keywords (e.g. termination: *terminate, notice, cancel, breach*), merged with reciprocal rank fusion (k=60); top 6 go to the model. Parties and start date also always include the first chunk (the preamble). Chat uses the same function with the question's keywords and top 8. Every query filters by `contract_id` and `user_id`.

## 13. Contract review methodology
One model call per item (temperature 0, JSON output, one retry on invalid JSON). The prompt (`app/review.py`) allows only `found`, `unclear`, `not_found`, requires a word-for-word quote from a single chunk, and treats contract text as data, not instructions. Page and section come from chunk metadata, never from the model.

## 14. Quote verification
`app/quotes.py`: the quote is normalized (whitespace, smart quotes, dashes, soft hyphens, ligatures only), then must be a substring of the cited chunk (or another retrieved chunk) and of the full contract text. Quotes containing ellipses are rejected. Failure -> status `unclear`, quote dropped. Chat answers get the same check: each quoted passage is marked verified or flagged "not found in the contract".

## 15. Chat and streaming
`POST /api/contracts/{id}/chat` returns Server-Sent Events (`token`, then `done` with verified citations, or `error`). The browser reads it with `fetch` so the auth header can be sent. The reply is saved when the stream completes; history reloads from `GET .../messages`. If the contract does not answer a question, the model must reply "The contract does not address this."

## 16. API documentation
All routes need `Authorization: Bearer <Clerk token>`.
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/contracts` | List own contracts |
| POST | `/api/contracts` | Upload (multipart `file`) -> 202 |
| GET | `/api/contracts/{id}` | Contract + findings |
| GET | `/api/contracts/{id}/text` | Full text (for highlighting) |
| POST | `/api/contracts/{id}/review` | Retry processing/review |
| DELETE | `/api/contracts/{id}` | Delete contract and everything under it |
| GET | `/api/contracts/{id}/messages` | Chat history |
| POST | `/api/contracts/{id}/chat` | Ask a question (SSE) |
Interactive docs: http://localhost:8000/docs

## 17. Installation instructions
Requires Docker. 
1. **Clerk:** create an application at dashboard.clerk.com (enable Email), copy the Publishable key and Secret key from *API Keys*.
2. **OpenRouter:** create a key at openrouter.ai/keys. Check openrouter.ai/models (search "free") that the chat and embedding model names in `.env` still exist.
3. `cp .env.example .env` and fill in the keys.
4. `docker compose up --build`
5. Open http://localhost:3000, sign up, upload a contract (samples in `backend/eval/samples/`).

Without Docker: run Postgres with pgvector, `pip install -r backend/requirements.txt && uvicorn app.main:app` (from `backend/`, with the env vars from `.env`), and `cd frontend && cp .env.local.example .env.local && npm install && npm run dev`.

## 18. Environment configuration
| Variable | Where | Meaning |
|---|---|---|
| `CLERK_PUBLISHABLE_KEY` | backend + frontend | Public key; also yields JWKS URL and issuer |
| `CLERK_SECRET_KEY` | frontend only | Clerk middleware |
| `CLERK_AUTHORIZED_PARTIES` | backend | Allowed `azp` origins |
| `OPENROUTER_API_KEY` | backend only | AI calls |
| `CHAT_MODEL`, `EMBED_MODEL`, `EMBED_DIM` | backend | Models; dimension must match the embedder |
| `NEXT_PUBLIC_API_URL` | frontend | Backend URL |
Changing `EMBED_DIM` after first run requires a fresh database volume (`docker compose down -v`).

## 19. Testing and evaluation
- Unit/API tests: `cd backend && pytest` (quote verification, chunk offsets and pages, grounding downgrade, JSON parsing, chat citations, 401 without or with a bad token).
- Evaluation: `docker compose exec backend python -m eval.run_eval` runs the real pipeline on two sample contracts (one lacks a liability cap and auto-renewal) and reports how many of 16 statuses match `eval/samples/expected.json`.

## 20. Security measures
Server-side JWT verification; user id never accepted from the client; all SQL filtered by `user_id` (including vector and keyword search); other users' ids return 404; upload extension, magic-byte and size checks; contract text is passed to the model as data; secrets only in `.env` (git-ignored).

## 21. Known limitations
- Scanned PDFs (no OCR) are rejected. 
- Chunking relies on heading patterns; unusual layouts may merge or split clauses badly. 
- DOCX/TXT have no page numbers. 
- A quote spanning two chunks is rejected (becomes `unclear`). 
- Free models are rate-limited and sometimes slow; a review of 8 items takes a minute or more. 
- The original file is not stored; retry reuses the extracted text. 
- Background jobs run in-process, so a restart interrupts them (marked failed, retry available). 
- Review is sequential; no per-user upload rate limiting.
- Not legal advice; findings need human review.

## 22. Future improvements
Job queue (e.g. Arq/Celery); OCR; cross-chunk quotes; re-ranking; contract version comparison; risk flags (e.g. no liability cap); larger evaluation set; automated multi-user isolation tests against a real database.

## 23. AI tools used
Claude was used to scaffold the codebase, draft the prompts and write tests; I reviewed the code and can explain each part. *(Edit this section to describe your own usage before submitting.)*

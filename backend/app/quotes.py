"""Quote verification: a quote is real only if it appears word for word in the contract text."""
import re
import unicodedata

_TRANS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00ad": None, "\u00a0": " ",
})
CITED = re.compile(r'["\u201c]([^"\u201d]{8,600})["\u201d]')


def normalize(s: str) -> str:
    """Neutralise PDF artefacts only (whitespace/line breaks, smart quotes, ligatures, soft hyphens)."""
    s = unicodedata.normalize("NFKC", s).translate(_TRANS)
    return re.sub(r"\s+", " ", s).strip()


def quote_in(quote: str | None, text: str) -> bool:
    if not quote or "..." in quote or "\u2026" in quote:
        return False
    nq = normalize(quote)
    return len(nq) >= 8 and nq in normalize(text)


def locate(quote: str | None, chunks: list[dict], preferred_id=None) -> dict | None:
    """Return the chunk containing the quote (preferred chunk first), or None."""
    ordered = sorted(chunks, key=lambda c: c["id"] != preferred_id)
    return next((c for c in ordered if quote_in(quote, c["text"])), None)


def citations_from_answer(answer: str, chunks: list[dict]) -> list[dict]:
    out = []
    for q in dict.fromkeys(m.group(1).strip() for m in CITED.finditer(answer)):
        c = locate(q, chunks)
        out.append(dict(
            quote=q, verified=c is not None, chunk_id=c["id"] if c else None,
            section_label=c["section_label"] if c else None, page=c["page_start"] if c else None,
            clause_text=c["text"] if c else None, char_start=c["char_start"] if c else None,
            char_end=c["char_end"] if c else None,
        ))
    return out

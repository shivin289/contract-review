"""Clause-aware chunking. Splits at headings/numbered clauses, never mid-sentence if avoidable,
and records page range, section label and character offsets for every chunk."""
import re
from bisect import bisect_right

HEADING = re.compile(
    r"^\s*(?:"
    r"\d{1,2}(?:\.\d{1,2})+\.?\s+\S"          # 5.1 Notice ...
    r"|\d{1,2}[.)]\s+\S"                       # 5. Termination / 5) Termination
    r"|(?i:article|section|clause)\s+[\w.]+"   # Article IV / Section 3
    r"|[A-Z][A-Z0-9 \-&,/]{3,60}\s*$"          # ALL-CAPS HEADING
    r")"
)
MIN_CHARS = 300   # do not split off a heading + tiny body; keep them together
MAX_CHARS = 2200  # long clauses are split at line/sentence boundaries


def chunk_text(full: str, spans: list[tuple[int, int, int | None]]) -> list[dict]:
    starts = [s for s, _, _ in spans]

    def page_at(i: int):
        return spans[max(bisect_right(starts, i) - 1, 0)][2]

    segments, seg_start, label, pos = [], 0, "Preamble", 0
    for line in full.split("\n"):
        if HEADING.match(line):
            if not full[seg_start:pos].strip():
                label = line.strip()[:90]
            elif pos - seg_start >= MIN_CHARS:
                segments.append((seg_start, pos, label))
                seg_start, label = pos, line.strip()[:90]
        pos += len(line) + 1
    segments.append((seg_start, len(full), label))

    pieces = []
    for s, e, lab in segments:
        first = True
        while e - s > MAX_CHARS:
            cut = full.rfind("\n", s + MAX_CHARS // 2, s + MAX_CHARS)
            if cut == -1:
                dot = full.rfind(". ", s + MAX_CHARS // 2, s + MAX_CHARS)
                cut = dot + 1 if dot != -1 else s + MAX_CHARS
            pieces.append((s, cut, lab if first else f"{lab} (cont.)"))
            s, first = cut, False
        pieces.append((s, e, lab if first else f"{lab} (cont.)"))

    chunks = []
    for s, e, lab in pieces:
        raw = full[s:e]
        s += len(raw) - len(raw.lstrip())
        text = full[s:e].rstrip()
        if len(text) < 3:
            continue
        e = s + len(text)
        chunks.append(
            dict(idx=len(chunks), section_label=lab, page_start=page_at(s), page_end=page_at(e - 1),
                 char_start=s, char_end=e, text=text)
        )
    return chunks

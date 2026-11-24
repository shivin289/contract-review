"""Text extraction. Returns pages as (page_number | None, text)."""
import io
import re

Page = tuple[int | None, str]


class ExtractionError(Exception):
    pass


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def _pdf(raw: bytes) -> list[Page]:
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(stream=raw, filetype="pdf")
        if doc.needs_pass:
            raise ExtractionError("The PDF is password protected.")
        return [(i + 1, page.get_text("text")) for i, page in enumerate(doc)]
    except ExtractionError:
        raise
    except Exception:
        raise ExtractionError("Could not open the PDF. The file may be corrupted.")


def _docx(raw: bytes) -> list[Page]:
    import docx

    try:
        document = docx.Document(io.BytesIO(raw))
    except Exception:
        raise ExtractionError("Could not open the DOCX. The file may be corrupted.")
    lines: list[str] = []
    for block in document.iter_inner_content():
        if hasattr(block, "rows"):
            for row in block.rows:
                lines.append(" | ".join(c.text.strip() for c in row.cells))
        else:
            lines.append(block.text)
    return [(None, "\n".join(lines))]  # DOCX has no stable page numbers: sections are used


def _txt(raw: bytes) -> list[Page]:
    text = raw.decode("utf-8", errors="replace")
    if "\f" in text:
        return [(i + 1, p) for i, p in enumerate(text.split("\f"))]
    return [(None, text)]


def extract_pages(filename: str, raw: bytes) -> list[Page]:
    ext = filename.rsplit(".", 1)[-1].lower()
    pages = {"pdf": _pdf, "docx": _docx, "txt": _txt}[ext](raw)
    pages = [(n, _clean(t)) for n, t in pages]
    if sum(len(t) for _, t in pages) < 50:
        raise ExtractionError("No readable text found. Scanned or image-only files are not supported.")
    return pages


def build_text(pages: list[Page]) -> tuple[str, list[tuple[int, int, int | None]]]:
    """Join pages into one string and remember which character range is which page."""
    full, spans = "", []
    for number, text in pages:
        start = len(full)
        full += text + "\n\n"
        spans.append((start, len(full), number))
    return full, spans

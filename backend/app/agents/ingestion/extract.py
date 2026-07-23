"""
app/agents/ingestion/extract.py

Document type detection and text extraction. Supports:
  PDF, DOCX, TXT, Markdown, images (OCR), bookmarks/webpages.

Extraction rules (03 §5.1):
  - Magic bytes first, extension as tiebreak (not the opposite).
  - Images and scanned PDFs without a text layer → OCR.
  - Bookmarks / webpages → trafilatura to strip nav/footer boilerplate.
"""

from __future__ import annotations

import io
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict

import structlog

from app.core.config import get_settings
from app.db.models.document import DocumentKind

log = structlog.get_logger(__name__)
settings = get_settings()

# --------------------------------------------------------------------------- #
# Public types                                                                  #
# --------------------------------------------------------------------------- #


class ExtractResult(TypedDict):
    text: str
    used_ocr: bool
    page_count: int | None


# --------------------------------------------------------------------------- #
# Type detection                                                                #
# --------------------------------------------------------------------------- #

# Minimal magic-byte signatures (offset, bytes)
_MAGIC: list[tuple[bytes, str]] = [
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "docx"),   # OOXML (also covers pptx/xlsx — tiebreak by ext)
    (b"\x89PNG", "image"),
    (b"\xff\xd8\xff", "image"),  # JPEG
    (b"GIF8", "image"),
    (b"BM", "image"),            # BMP
    (b"\x00\x00\x01\x00", "image"),  # ICO
]

_EXT_MIME_MAP: dict[str, tuple[DocumentKind, str]] = {
    ".pdf":  (DocumentKind.pdf,      "application/pdf"),
    ".docx": (DocumentKind.docx,     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".txt":  (DocumentKind.txt,      "text/plain"),
    ".md":   (DocumentKind.md,       "text/markdown"),
    ".markdown": (DocumentKind.md,   "text/markdown"),
    ".png":  (DocumentKind.image,    "image/png"),
    ".jpg":  (DocumentKind.image,    "image/jpeg"),
    ".jpeg": (DocumentKind.image,    "image/jpeg"),
    ".gif":  (DocumentKind.image,    "image/gif"),
    ".bmp":  (DocumentKind.image,    "image/bmp"),
    ".webp": (DocumentKind.image,    "image/webp"),
    ".tiff": (DocumentKind.image,    "image/tiff"),
    ".tif":  (DocumentKind.image,    "image/tiff"),
}


def detect_kind(raw: bytes, filename: str) -> tuple[DocumentKind, str]:
    """
    Return (DocumentKind, mime_type) by inspecting magic bytes first,
    then using the file extension as a tiebreak for ambiguous types.
    """
    # 1. Magic bytes
    header = raw[:8]
    magic_kind: str | None = None
    for signature, kind_str in _MAGIC:
        if header.startswith(signature):
            magic_kind = kind_str
            break

    # 2. Extension tiebreak / fallback
    ext = Path(filename).suffix.lower()
    ext_entry = _EXT_MIME_MAP.get(ext)

    if magic_kind == "docx" and ext in {".xlsx", ".pptx"}:
        # All OOXML share the PK header — disambiguate by extension
        return (DocumentKind.txt, "application/octet-stream")

    if magic_kind == "pdf":
        return (DocumentKind.pdf, "application/pdf")
    if magic_kind == "image":
        mime = ext_entry[1] if ext_entry else "image/png"
        return (DocumentKind.image, mime)
    if magic_kind == "docx":
        return (DocumentKind.docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    # Fall back to extension
    if ext_entry:
        return ext_entry

    # Plain text is the safe default for unknown files
    return (DocumentKind.txt, "text/plain")


# --------------------------------------------------------------------------- #
# Text extraction per kind                                                      #
# --------------------------------------------------------------------------- #


def _has_pdf_text_layer(raw: bytes) -> bool:
    """Quick heuristic: return True if the PDF has extractable text."""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(raw))
        for page in reader.pages[:3]:   # check first 3 pages only
            if page.extract_text():
                return True
        return False
    except Exception:
        return False


def _extract_pdf(raw: bytes) -> tuple[str, int]:
    """Extract text from a searchable PDF. Returns (text, page_count)."""
    import pdfplumber

    pages_text: list[str] = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            pages_text.append(t)
    return "\n\n".join(pages_text), len(pages_text)


def _extract_docx(raw: bytes) -> str:
    """Extract text from a DOCX file."""
    import docx

    doc = docx.Document(io.BytesIO(raw))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def _extract_markdown(raw: bytes) -> str:
    """Strip Markdown syntax and return plain text."""
    import re

    text = raw.decode("utf-8", errors="replace")
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    # Remove headings markup but keep text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove links/images — keep display text
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Remove bold/italic
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    return text


def _extract_webpage(raw: bytes) -> str:
    """
    Strip navigation/footer boilerplate from HTML using trafilatura.
    Falls back to raw decoded text on failure.
    """
    try:
        import trafilatura

        html = raw.decode("utf-8", errors="replace")
        result = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )
        return result or html
    except Exception as exc:
        log.warning("trafilatura extraction failed", error=str(exc))
        return raw.decode("utf-8", errors="replace")


def _ocr_bytes(raw: bytes, mime: str) -> str:
    """
    Run OCR on image bytes or a scanned PDF.
    Uses pytesseract by default; EasyOCR if PKMS_OCR_ENGINE=easyocr.
    """
    from PIL import Image

    if settings.pkms_ocr_engine == "easyocr":
        return _ocr_easyocr(raw, mime)

    # pytesseract path
    if "pdf" in mime:
        # Convert PDF pages to images first using subprocess (pdftoppm)
        return _ocr_pdf_pytesseract(raw)

    img = Image.open(io.BytesIO(raw))
    import pytesseract

    return pytesseract.image_to_string(img, config="--psm 3")


def _ocr_pdf_pytesseract(raw: bytes) -> str:
    """Convert each PDF page to a PNG and OCR it with pytesseract."""
    import pytesseract
    from PIL import Image

    try:
        # Use pypdf's page-as-image via pdftoppm subprocess
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "input.pdf"
            pdf_path.write_bytes(raw)
            out_prefix = Path(tmpdir) / "page"
            subprocess.run(
                ["pdftoppm", "-r", "200", "-png", str(pdf_path), str(out_prefix)],
                check=True,
                timeout=120,
                capture_output=True,
            )
            pages = sorted(Path(tmpdir).glob("page-*.png"))
            texts = []
            for pg in pages:
                img = Image.open(pg)
                texts.append(pytesseract.image_to_string(img, config="--psm 3"))
            return "\n\n".join(texts)
    except Exception as exc:
        log.warning("PDF OCR via pdftoppm failed", error=str(exc))
        # Fallback: read as single image
        try:
            img = Image.open(io.BytesIO(raw))
            import pytesseract as pt
            return pt.image_to_string(img)
        except Exception:
            return ""


def _ocr_easyocr(raw: bytes, mime: str) -> str:
    """EasyOCR fallback — only loaded if PKMS_OCR_ENGINE=easyocr."""
    try:
        import easyocr
        import numpy as np
        from PIL import Image

        reader = easyocr.Reader(["en"], gpu=(settings.pkms_embed_device == "cuda"))
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        arr = np.array(img)
        results = reader.readtext(arr, detail=0)
        return " ".join(results)
    except Exception as exc:
        log.error("EasyOCR failed", error=str(exc))
        return ""


# --------------------------------------------------------------------------- #
# Public entry point                                                            #
# --------------------------------------------------------------------------- #


def extract_text(raw: bytes, kind: str, mime: str) -> ExtractResult:
    """
    Extract plain text from *raw* bytes given the detected *kind* and *mime*.

    Returns an ExtractResult with keys: ``text``, ``used_ocr``, ``page_count``.
    Raises ``ValueError`` if the kind is unsupported.
    """
    used_ocr = False
    page_count: int | None = None

    if kind == DocumentKind.pdf.value or kind == "pdf":
        if _has_pdf_text_layer(raw):
            text, page_count = _extract_pdf(raw)
        else:
            log.info("PDF has no text layer — falling back to OCR")
            text = _ocr_bytes(raw, mime)
            used_ocr = True

    elif kind in (DocumentKind.docx.value, "docx"):
        text = _extract_docx(raw)

    elif kind in (DocumentKind.image.value, "image"):
        text = _ocr_bytes(raw, mime)
        used_ocr = True

    elif kind in (DocumentKind.txt.value, "txt"):
        text = raw.decode("utf-8", errors="replace")

    elif kind in (DocumentKind.md.value, "md"):
        text = _extract_markdown(raw)

    elif kind in (DocumentKind.bookmark.value, "bookmark"):
        text = _extract_webpage(raw)

    elif kind in (DocumentKind.note.value, "note"):
        text = raw.decode("utf-8", errors="replace")

    else:
        raise ValueError(f"Unsupported document kind: {kind!r}")

    return ExtractResult(text=text, used_ocr=used_ocr, page_count=page_count)

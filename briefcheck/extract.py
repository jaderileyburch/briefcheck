"""Brief text extraction.

Plain text and Markdown work with no extra dependencies. PDF and Word support
load only if the optional libraries are installed, so the core tool stays
dependency-light.
"""
from __future__ import annotations

from pathlib import Path


def extract_text(path: str | Path) -> str:
    """Return the text of a complaint file. Supports .txt, .md, .pdf, .docx."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    suffix = p.suffix.lower()

    if suffix in (".txt", ".md", ""):
        return p.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        return _extract_pdf(p)

    if suffix in (".docx",):
        return _extract_docx(p)

    # Unknown extension: try plain text.
    return p.read_text(encoding="utf-8", errors="replace")


def _extract_pdf(p: Path) -> str:
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            raise RuntimeError(
                "Reading PDF requires 'pdfplumber' or 'pypdf'. Install one "
                "(pip install pdfplumber) or convert the brief to a .txt file."
            )
        reader = PdfReader(str(p))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    with pdfplumber.open(str(p)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _extract_docx(p: Path) -> str:
    try:
        import docx  # type: ignore
    except ImportError:
        raise RuntimeError(
            "Reading .docx requires 'python-docx'. Install it "
            "(pip install python-docx) or convert the brief to a .txt file."
        )
    document = docx.Document(str(p))
    return "\n".join(par.text for par in document.paragraphs)

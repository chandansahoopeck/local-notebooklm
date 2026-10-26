import re
import subprocess
import tempfile
from pathlib import Path

import pymupdf
import trafilatura
from youtube_transcript_api import YouTubeTranscriptApi

from . import config, llm, store

BATCH = 32
YOUTUBE_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([\w-]{11})")


def _has_text(doc: pymupdf.Document) -> bool:
    """Check if PDF has extractable text."""
    for page in doc:
        if page.get_text().strip():
            return True
    return False


def _ocr_pdf(data: bytes) -> bytes:
    """Run OCR on scanned PDF using ocrmypdf."""
    try:
        import ocrmypdf
    except ImportError:
        raise ImportError(
            "OCR is required for scanned PDFs. Install with: pip install ocrmypdf"
        )
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
        tmp_in.write(data)
        tmp_in_path = tmp_in.name
    
    tmp_out_path = tmp_in_path + ".ocr.pdf"
    
    try:
        ocrmypdf.ocr(
            tmp_in_path,
            tmp_out_path,
            language="eng",
            deskew=True,
            cleanup=True,
        )
        with open(tmp_out_path, "rb") as f:
            ocr_data = f.read()
        return ocr_data
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)
        Path(tmp_out_path).unlink(missing_ok=True)


def _chunks(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    step = config.CHUNK_SIZE - config.CHUNK_OVERLAP
    for start in range(0, len(text), step):
        yield start, text[start:start + config.CHUNK_SIZE]
        if start + config.CHUNK_SIZE >= len(text):
            break


def _index(notebook: str, source: str, pages: list[tuple[int, str]]) -> int:
    store.delete_source(notebook, source)
    ids, docs, metas = [], [], []
    for page, text in pages:
        for start, piece in _chunks(text):
            ids.append(f"{notebook}|{source}|{page}|{start}")
            docs.append(piece)
            metas.append({"notebook": notebook, "source": source, "page": page, "start": start})
    if not docs:
        raise ValueError(f"No text found in {source} (scanned PDF? run OCR first).")
    for i in range(0, len(docs), BATCH):
        batch = docs[i:i + BATCH]
        store.add(ids[i:i + BATCH], batch, llm.embed(batch), metas[i:i + BATCH])
    return len(docs)


def ingest_pdf(notebook: str, name: str, data: bytes) -> int:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        # Check if PDF has text
        if not _has_text(doc):
            print(f"⚠️  {name} appears to be a scanned PDF. Running OCR...")
            data = _ocr_pdf(data)
            # Re-open the OCR-processed PDF
            with pymupdf.open(stream=data, filetype="pdf") as doc_ocr:
                pages = [(n, page.get_text()) for n, page in enumerate(doc_ocr, 1)]
        else:
            pages = [(n, page.get_text()) for n, page in enumerate(doc, 1)]
    return _index(notebook, name, pages)


def ingest_text(notebook: str, name: str, text: str) -> int:
    return _index(notebook, name, [(0, text)])


def ingest_url(notebook: str, url: str) -> int:
    html = trafilatura.fetch_url(url)
    text = trafilatura.extract(html) if html else None
    if not text:
        raise ValueError(f"Could not extract text from {url}")
    return _index(notebook, url, [(0, text)])


def is_youtube(url: str) -> bool:
    return ("youtube" in url or "youtu.be" in url) and bool(YOUTUBE_ID.search(url))


def ingest_youtube(notebook: str, url: str) -> int:
    match = YOUTUBE_ID.search(url)
    if not match:
        raise ValueError("Not a valid YouTube URL")
    transcript = YouTubeTranscriptApi().fetch(match.group(1))
    return _index(notebook, url, [(0, " ".join(s.text for s in transcript))])
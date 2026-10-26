import hashlib
from pathlib import Path

import chromadb
from chromadb.config import Settings

from . import config

_client = chromadb.PersistentClient(
    path=str(config.CHROMA_DIR), settings=Settings(anonymized_telemetry=False)
)
collection = _client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"})


def _where(notebook: str, sources: list[str] | None = None) -> dict:
    if sources:
        return {"$and": [{"notebook": notebook}, {"source": {"$in": list(sources)}}]}
    return {"notebook": notebook}


def add(ids, documents, embeddings, metadatas) -> None:
    collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)


def search(embedding, notebook, sources=None, k=config.TOP_K) -> list[dict]:
    if collection.count() == 0:
        return []
    r = collection.query(
        query_embeddings=[embedding],
        n_results=k,
        where=_where(notebook, sources),
        include=["documents", "metadatas"],
    )
    return [{"text": d, **m} for d, m in zip(r["documents"][0], r["metadatas"][0])]


def list_notebooks() -> list[str]:
    metas = collection.get(include=["metadatas"])["metadatas"]
    return sorted({m["notebook"] for m in metas})


def list_sources(notebook: str) -> list[str]:
    metas = collection.get(where=_where(notebook), include=["metadatas"])["metadatas"]
    return sorted({m["source"] for m in metas})


def get_texts(notebook: str, sources=None) -> dict[str, str]:
    r = collection.get(where=_where(notebook, sources), include=["documents", "metadatas"])
    rows = sorted(
        zip(r["metadatas"], r["documents"]),
        key=lambda row: (row[0]["source"], row[0]["page"], row[0]["start"]),
    )
    texts: dict[str, list[str]] = {}
    for meta, doc in rows:
        # chunks overlap, so drop the repeated prefix when stitching
        texts.setdefault(meta["source"], []).append(doc[config.CHUNK_OVERLAP:] if meta["start"] else doc)
    return {source: " ".join(parts) for source, parts in texts.items()}


def digest_path(notebook: str, source: str) -> Path:
    key = hashlib.sha256(f"{notebook}|{source}".encode()).hexdigest()[:32]
    return config.DIGEST_DIR / f"{key}.md"


def delete_source(notebook: str, source: str) -> None:
    collection.delete(where=_where(notebook, [source]))
    digest_path(notebook, source).unlink(missing_ok=True)

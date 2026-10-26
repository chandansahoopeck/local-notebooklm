import os
import re
from pathlib import Path

LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
CHROMA_DIR = DATA_DIR / "chroma"
DIGEST_DIR = DATA_DIR / "digests"
OUTPUT_DIR = DATA_DIR / "outputs"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
TOP_K = 6
MAX_MATERIAL_CHARS = 12000  # ~3k tokens, leaves room in NUM_CTX for the output

for _dir in (CHROMA_DIR, DIGEST_DIR, OUTPUT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def output_dir(notebook: str) -> Path:
    path = OUTPUT_DIR / re.sub(r"[^\w-]+", "_", notebook)
    path.mkdir(parents=True, exist_ok=True)
    return path

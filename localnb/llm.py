import json

import ollama

from . import config


def embed(texts: list[str]) -> list[list[float]]:
    return ollama.embed(model=config.EMBED_MODEL, input=texts)["embeddings"]


def chat(messages: list[dict], json_mode: bool = False) -> str:
    response = ollama.chat(
        model=config.LLM_MODEL,
        messages=messages,
        format="json" if json_mode else None,
        options={"num_ctx": config.NUM_CTX},
    )
    return response["message"]["content"]


def ask(prompt: str) -> str:
    return chat([{"role": "user", "content": prompt}])


def ask_json(prompt: str) -> dict:
    raw = chat([{"role": "user", "content": prompt}], json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {raw[:200]}") from e


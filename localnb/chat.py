from . import llm, store

SYSTEM = (
    "You are a research assistant. Answer ONLY from the numbered sources provided. "
    "Cite every claim with its source number, like [1] or [2][3]. "
    "If the sources don't contain the answer, say \"I couldn't find that in your sources.\""
)


def _label(meta: dict) -> str:
    return f"{meta['source']} (p. {meta['page']})" if meta["page"] else meta["source"]


def ask(notebook: str, question: str, history=None, sources=None):
    hits = store.search(llm.embed([question])[0], notebook, sources)
    if not hits:
        return "This notebook has no sources yet.", []
    for hit in hits:
        hit["label"] = _label(hit)

    context = "\n\n".join(f"[{i}] {h['label']}\n{h['text']}" for i, h in enumerate(hits, 1))
    messages = [{"role": "system", "content": SYSTEM}]
    messages += [{"role": m["role"], "content": m["content"]} for m in (history or [])[-6:]]
    messages.append({"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {question}"})
    return llm.chat(messages), hits

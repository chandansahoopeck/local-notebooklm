import itertools

from . import config, llm, store

BULLETS = """Extract the key points, facts, names and numbers from this text as concise Markdown bullets. Use only the text.

{text}"""

BRIEFING = """Write a briefing document in Markdown based only on the material below.
Include a 3-sentence **Executive Summary**, a **Key Themes** section with a short paragraph per theme,
and **Important Facts & Figures** as bullets.

Material:
{material}"""

FAQ = """Write 8 frequently asked questions a newcomer would ask about the material below, each with a clear answer.
Format each as '### Question' followed by the answer. Use only the material.

Material:
{material}"""

STUDY_GUIDE = """Create a study guide in Markdown from the material below with:
1. **Key Concepts** - term: one-line definition
2. **Quiz** - 5 short-answer questions
3. **Answer Key**
Use only the material.

Material:
{material}"""

MIND_MAP = """Create a hierarchical mind map of the material below.
Return JSON shaped like {{"title": "Main topic", "children": [{{"title": "Branch", "children": [{{"title": "Leaf", "children": []}}]}}]}}.
Use 4-7 main branches, at most 3 levels deep, and titles under 6 words.

Material:
{material}"""


def _split(text: str, size: int = config.MAX_MATERIAL_CHARS) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def _digest(notebook: str, source: str, text: str) -> str:
    path = store.digest_path(notebook, source)
    if path.exists():
        return path.read_text(encoding="utf-8")
    if len(text) <= config.MAX_MATERIAL_CHARS // 2:
        body = text
    else:
        body = "\n".join(llm.ask(BULLETS.format(text=part)) for part in _split(text))
    digest = f"## {source}\n{body}"
    path.write_text(digest, encoding="utf-8")
    return digest


def material(notebook: str, sources=None) -> str:
    """Map-reduce the selected sources into text that fits the model's context."""
    texts = store.get_texts(notebook, sources)
    if not texts:
        raise ValueError("Add sources to this notebook first.")
    combined = "\n\n".join(_digest(notebook, s, t) for s, t in texts.items())
    for _ in range(3):
        if len(combined) <= config.MAX_MATERIAL_CHARS:
            break
        combined = "\n".join(llm.ask(BULLETS.format(text=part)) for part in _split(combined))
    return combined[: config.MAX_MATERIAL_CHARS]


def briefing(notebook: str, sources=None) -> str:
    return llm.ask(BRIEFING.format(material=material(notebook, sources)))


def faq(notebook: str, sources=None) -> str:
    return llm.ask(FAQ.format(material=material(notebook, sources)))


def study_guide(notebook: str, sources=None) -> str:
    return llm.ask(STUDY_GUIDE.format(material=material(notebook, sources)))


def mind_map(notebook: str, sources=None) -> dict:
    return llm.ask_json(MIND_MAP.format(material=material(notebook, sources)))


def mind_map_dot(tree: dict) -> str:
    lines = [
        "digraph G {",
        "rankdir=LR;",
        'node [shape=box, style="rounded,filled", fillcolor="#eef2ff", fontname="Helvetica"];',
    ]
    ids = itertools.count()

    def walk(node: dict, parent: str | None = None) -> None:
        node_id = f"n{next(ids)}"
        label = str(node.get("title", "")).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{node_id} [label="{label}"];')
        if parent:
            lines.append(f"{parent} -> {node_id};")
        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child, node_id)

    walk(tree)
    lines.append("}")
    return "\n".join(lines)

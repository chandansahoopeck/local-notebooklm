import json
from functools import lru_cache

import numpy as np
import soundfile as sf

from . import config, llm, studio

SAMPLE_RATE = 24000
HOSTS = {"Alex": "af_heart", "Sam": "am_michael"}

PODCAST = """Write a highly detailed, lively podcast conversation between two hosts, Alex and Sam, explaining the material below to a curious listener.
- Alex guides the conversation and asks deep, probing questions; Sam explains with concrete examples and thorough explanations.
- Open with a strong hook, cover the most important ideas in depth, and close with a comprehensive recap.
- Aim for about {turns} turns. Each turn should be 3-5 sentences long, natural spoken style, no stage directions.
- Use only facts from the material, but expand on them to ensure a lengthy, engaging discussion.
Return JSON shaped like {{"lines": [{{"speaker": "Alex", "text": "..."}}, {{"speaker": "Sam", "text": "..."}}]}}.

Material:
{material}"""


@lru_cache(maxsize=1)
def _pipeline():
    from kokoro import KPipeline  # pulls in torch; import only when audio is needed
    return KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")


def synthesize(text: str, voice: str) -> np.ndarray:
    parts = [np.asarray(a, dtype=np.float32) for _, _, a in _pipeline()(text, voice=voice) if a is not None]
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


def podcast(notebook: str, sources=None, turns: int = 80):
    data = llm.ask_json(PODCAST.format(turns=turns, material=studio.material(notebook, sources)))
    lines = [l for l in data.get("lines", []) if isinstance(l, dict) and l.get("text")]
    if not lines:
        raise ValueError("Model returned an empty script; try again or use a larger model.")

    voices = list(HOSTS.values())
    clips = []
    for i, line in enumerate(lines):
        voice = HOSTS.get(line.get("speaker")) or voices[i % 2]
        clips += [synthesize(line["text"], voice), silence(0.25)]

    out_dir = config.output_dir(notebook)
    path = out_dir / "audio_overview.wav"
    sf.write(path, np.concatenate(clips), SAMPLE_RATE)
    (out_dir / "audio_overview.json").write_text(json.dumps(lines, indent=2), encoding="utf-8")
    return path, lines

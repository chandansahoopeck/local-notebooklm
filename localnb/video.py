import textwrap
from pathlib import Path

import numpy as np
import soundfile as sf
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont

from . import audio, config, llm, studio

W, H = 1280, 720
VOICE = "af_heart"
FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

VIDEO = """Turn the material below into a {slides}-slide explainer video.
For each slide give a short title, 2-4 bullet points (under 10 words each),
and narration of 2-4 spoken sentences that explains the slide. Use only the material.
Return JSON shaped like {{"scenes": [{{"title": "...", "bullets": ["..."], "narration": "..."}}]}}.

Material:
{material}"""


def _font(size: int):
    for path in FONT_PATHS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _render_slide(scene: dict, index: int, total: int, path: Path) -> None:
    img = Image.new("RGB", (W, H), (18, 24, 38))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 8], fill=(99, 102, 241))
    title_font, body_font, small_font = _font(54), _font(34), _font(22)

    y = 70
    for line in textwrap.wrap(str(scene.get("title", "")), 38):
        draw.text((80, y), line, font=title_font, fill="white")
        y += 66
    y += 30
    for bullet in (scene.get("bullets") or [])[:5]:
        draw.text((80, y), "•", font=body_font, fill=(129, 140, 248))
        for line in textwrap.wrap(str(bullet), 60) or [""]:
            draw.text((120, y), line, font=body_font, fill=(226, 232, 240))
            y += 46
        y += 14
    draw.text((W - 120, H - 50), f"{index}/{total}", font=small_font, fill=(148, 163, 184))
    img.save(path)


def explainer(notebook: str, sources=None, slides: int = 6) -> Path:
    data = llm.ask_json(VIDEO.format(slides=slides, material=studio.material(notebook, sources)))
    scenes = [s for s in data.get("scenes", []) if isinstance(s, dict) and s.get("narration")]
    if not scenes:
        raise ValueError("Model returned no scenes; try again or use a larger model.")

    work = config.output_dir(notebook) / "video_parts"
    work.mkdir(exist_ok=True)
    clips, narrations = [], []
    for i, scene in enumerate(scenes, 1):
        img, wav = work / f"slide_{i:02d}.png", work / f"slide_{i:02d}.wav"
        _render_slide(scene, i, len(scenes), img)
        speech = np.concatenate([audio.synthesize(scene["narration"], VOICE), audio.silence(0.6)])
        sf.write(wav, speech, audio.SAMPLE_RATE)
        narration = AudioFileClip(str(wav))
        narrations.append(narration)
        clips.append(ImageClip(str(img)).with_duration(narration.duration).with_audio(narration))

    out = config.output_dir(notebook) / "video_overview.mp4"
    final = concatenate_videoclips(clips)
    final.write_videofile(str(out), fps=24, codec="libx264", audio_codec="aac", logger=None)
    for clip in [final, *clips, *narrations]:
        clip.close()
    return out

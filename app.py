import streamlit as st
import json
from pathlib import Path

from localnb import audio, chat, ingest, store, studio, video, config

st.set_page_config(page_title="Local NotebookLM", layout="wide")
ss = st.session_state
ss.setdefault("notebook", "default")
ss.setdefault("chats", {})
ss.setdefault("artifacts", {})


def load_existing_artifacts(nb: str):
    """Load previously generated files from disk into session state."""
    if nb not in ss.artifacts:
        ss.artifacts[nb] = {}
    
    arts = ss.artifacts[nb]
    out_dir = config.output_dir(nb)
    
    # Load Audio
    audio_path = out_dir / "audio_overview.wav"
    audio_json = out_dir / "audio_overview.json"
    if audio_path.exists() and audio_json.exists():
        with open(audio_json, "r", encoding="utf-8") as f:
            lines = json.load(f)
        arts["Audio overview"] = (audio_path, lines)
        
    # Load Video
    video_path = out_dir / "video_overview.mp4"
    if video_path.exists():
        arts["Video overview"] = video_path
        
    # Load Text artifacts
    for name in ["Briefing doc", "FAQ", "Study guide"]:
        file_name = f"{name.replace(' ', '_').lower()}.md"
        file_path = out_dir / file_name
        if file_path.exists():
            arts[name] = file_path.read_text(encoding="utf-8")
            
    # Load Mind map
    mindmap_path = out_dir / "mind_map.json"
    if mindmap_path.exists():
        with open(mindmap_path, "r", encoding="utf-8") as f:
            arts["Mind map"] = json.load(f)


# Load artifacts for the current notebook on startup
load_existing_artifacts(ss.notebook)


def attempt(label, fn, *args):
    try:
        with st.spinner(f"{label}..."):
            return fn(*args)
    except Exception as e:
        st.error(f"{label} failed: {e}")
        return None


def show_citations(cites):
    if not cites:
        return
    with st.expander(f"Sources ({len(cites)})"):
        for i, c in enumerate(cites, 1):
            st.markdown(f"**[{i}] {c['label']}**")
            st.caption(c["text"][:500])


# ---------------- Sidebar: notebooks + sources ----------------
with st.sidebar:
    st.header("Notebook")
    names = sorted(set(store.list_notebooks()) | {ss.notebook})
    picked = st.selectbox("Open", names, index=names.index(ss.notebook))
    if picked != ss.notebook:
        ss.notebook = picked
        load_existing_artifacts(picked) # Load artifacts for the newly selected notebook
        st.rerun()
        
    new_name = st.text_input("New notebook")
    if st.button("Create") and new_name.strip():
        ss.notebook = new_name.strip()
        load_existing_artifacts(ss.notebook)
        st.rerun()
    nb = ss.notebook

    st.divider()
    st.header("Add sources")
    files = st.file_uploader("PDF / TXT / MD", type=["pdf", "txt", "md"], accept_multiple_files=True)
    if st.button("Add files", disabled=not files):
        for f in files:
            if f.name.lower().endswith(".pdf"):
                n = attempt(f"Indexing {f.name}", ingest.ingest_pdf, nb, f.name, f.getvalue())
            else:
                text = f.getvalue().decode("utf-8", errors="ignore")
                n = attempt(f"Indexing {f.name}", ingest.ingest_text, nb, f.name, text)
            if n is not None:
                st.success(f"{f.name}: {n} chunks")

    url = st.text_input("Web page or YouTube URL").strip()
    if st.button("Add URL", disabled=not url):
        fn = ingest.ingest_youtube if ingest.is_youtube(url) else ingest.ingest_url
        n = attempt(f"Indexing {url}", fn, nb, url)
        if n is not None:
            st.success(f"Added {n} chunks")

    st.divider()
    st.header("Sources")
    sources = store.list_sources(nb)
    selected = st.multiselect("Use these sources", sources, default=sources)
    for s in sources:
        left, right = st.columns([5, 1])
        left.caption(s)
        if right.button("✕", key=f"del-{s}"):
            store.delete_source(nb, s)
            st.rerun()


# ---------------- Main: Chat + Studio ----------------
st.title(nb)
chat_tab, studio_tab = st.tabs(["Chat", "Studio"])

with chat_tab:
    history = ss.chats.setdefault(nb, [])
    box = st.container()
    question = st.chat_input("Ask about your sources", disabled=not selected)
    if st.button("Clear chat"):
        history.clear()
        st.rerun()
    with box:
        for m in history:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                show_citations(m.get("citations"))
        if question:
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                result = attempt("Thinking", chat.ask, nb, question, history, selected)
                if result:
                    answer, cites = result
                    st.markdown(answer)
                    show_citations(cites)
                    history.append({"role": "user", "content": question})
                    history.append({"role": "assistant", "content": answer, "citations": cites})

with studio_tab:
    arts = ss.artifacts.setdefault(nb, {})
    if not selected:
        st.info("Add or select sources in the sidebar first.")
    text_tools = {"Briefing doc": studio.briefing, "FAQ": studio.faq, "Study guide": studio.study_guide}

    row1 = st.columns(3)
    for col, (name, fn) in zip(row1, text_tools.items()):
        if col.button(name, disabled=not selected):
            result = attempt(f"Generating {name}", fn, nb, selected)
            if result:
                arts[name] = result
                # SAVE TO DISK FOR PERSISTENCE
                file_path = config.output_dir(nb) / f"{name.replace(' ', '_').lower()}.md"
                file_path.write_text(result, encoding="utf-8")

    row2 = st.columns(3)
    if row2[0].button("Mind map", disabled=not selected):
        result = attempt("Generating mind map", studio.mind_map, nb, selected)
        if result:
            arts["Mind map"] = result
            # SAVE TO DISK FOR PERSISTENCE
            file_path = config.output_dir(nb) / "mind_map.json"
            file_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            
    if row2[1].button("Audio overview", disabled=not selected):
        result = attempt("Generating podcast (takes a few minutes)", audio.podcast, nb, selected)
        if result:
            arts["Audio overview"] = result
            
    if row2[2].button("Video overview", disabled=not selected):
        result = attempt("Generating video (takes a few minutes)", video.explainer, nb, selected)
        if result:
            arts["Video overview"] = result

    for name in text_tools:
        if arts.get(name):
            with st.expander(name, expanded=True):
                st.markdown(arts[name])
                st.download_button("Download .md", arts[name], file_name=f"{name}.md", key=f"dl-{name}")

    if arts.get("Mind map"):
        with st.expander("Mind map", expanded=True):
            st.graphviz_chart(studio.mind_map_dot(arts["Mind map"]))

    if arts.get("Audio overview"):
        path, lines = arts["Audio overview"]
        with st.expander("Audio overview", expanded=True):
            st.audio(str(path))
            st.download_button("Download .wav", path.read_bytes(), file_name="audio_overview.wav", key="dl-audio")
            st.markdown("\n\n".join(f"**{l.get('speaker', '?')}:** {l['text']}" for l in lines))

    if arts.get("Video overview"):
        path = arts["Video overview"]
        with st.expander("Video overview", expanded=True):
            st.video(str(path))
            st.download_button("Download .mp4", path.read_bytes(), file_name="video_overview.mp4", key="dl-video")
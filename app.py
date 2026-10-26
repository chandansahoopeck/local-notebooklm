import streamlit as st

from localnb import audio, chat, ingest, store, studio, video

st.set_page_config(page_title="Local NotebookLM", layout="wide")
ss = st.session_state
ss.setdefault("notebook", "default")
ss.setdefault("chats", {})
ss.setdefault("artifacts", {})


def attempt(label, fn, *args):
    try:
        with st.spinner(f"{label}..."):
            return fn(*args)
    except Exception as e:  # show Ollama/parsing errors in the UI instead of crashing
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
        st.rerun()
    new_name = st.text_input("New notebook")
    if st.button("Create") and new_name.strip():
        ss.notebook = new_name.strip()
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
            arts[name] = attempt(f"Generating {name}", fn, nb, selected)

    row2 = st.columns(3)
    if row2[0].button("Mind map", disabled=not selected):
        arts["Mind map"] = attempt("Generating mind map", studio.mind_map, nb, selected)
    if row2[1].button("Audio overview", disabled=not selected):
        arts["Audio overview"] = attempt("Generating podcast (takes a few minutes)", audio.podcast, nb, selected)
    if row2[2].button("Video overview", disabled=not selected):
        arts["Video overview"] = attempt("Generating video (takes a few minutes)", video.explainer, nb, selected)

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

# Local NotebookLM

A local, privacy-focused alternative to Google's NotebookLM using Ollama for AI inference.

## Features
-  Upload PDFs, TXT, MD files, web pages, and YouTube videos
-  Chat with your documents
-  Studio tools: Briefing docs, FAQs, Study guides, Mind maps
- 🎵 Audio podcast generation
- 🎥 Video explainer generation

## Requirements
- macOS with Homebrew
- Python 3.12+
- Ollama

## Installation

```bash
# Install dependencies
brew install python@3.12 ffmpeg espeak-ng ollama
brew services start ollama

# Pull models
ollama pull qwen2.5:7b
ollama pull bge-m3

# Setup project
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
streamlit run app.py

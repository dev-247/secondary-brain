# Welcome to Your Second Brain

This is a starter note. Drop PDFs, Markdown, images, and text files into `vault/` and run:

```bash
python main.py ingest
python main.py ask "What is this project?"
```

## Core Principles

- **Privacy first:** Your files stay local. Only retrieved snippets go to LLMs.
- **Provenance:** Every answer should cite its source file and section.
- **Hybrid search:** Semantic vectors plus keyword (BM25) retrieval for precision.

## Getting Started

1. Start Qdrant: `docker compose up -d`
2. Pull Ollama models: `ollama pull nomic-embed-text` and `ollama pull llama3.2`
3. Copy `.env.example` to `.env` and add your OpenRouter key for deep queries
4. Ingest your vault and start asking questions

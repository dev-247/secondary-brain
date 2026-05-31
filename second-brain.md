# Product Specification: Personal "Second Brain" Intelligence

## 1. Mission & Philosophy
Build a privacy-first, local-running AI knowledge assistant that synthesizes documents (PDFs, images, Markdown) into actionable insights. 
- **Privacy:** Data stays local. Only snippets are sent to external reasoning engines.
- **Provenance:** Every AI claim must cite its source file and location.
- **Hybrid-First:** Use Vector (Semantic) + Lexical (BM25) search for high-precision retrieval.

## 2. Technical Stack
- **OS/Hardware:** macOS (M4 Apple Silicon) - Leverage Metal acceleration.
- **Language:** Python 3.12+ (managed by `uv`).
- **Core Infrastructure:** Docker Compose (Qdrant for vector/hybrid storage).
- **Ingestion:** Docling (for layout-aware parsing of PDFs/tables/images).
- **Inference Engine:** - **Local:** Ollama (Llama 3.2/Mistral) for embeddings/routine tasks.
  - **Fallback (Cloud):** OpenRouter API (for complex synthesis using models like Claude 3.5 Sonnet).

## 3. Directory Structure

/
├── .env                # API keys and environment variables
├── docker-compose.yml  # Qdrant container definition
├── SECOND_BRAIN_SPEC.md # This specification
├── vault/              # Input directory (PDFs, MD, Images, Docs)
├── wiki/               # Output directory (AI-organized knowledge)
├── scripts/
│   ├── ingest.py       # Docling pipeline + Qdrant upsert
│   ├── search.py       # Hybrid retrieval + Reranking logic
│   ├── router.py       # LLM provider switching (Local vs. Cloud)
│   └── audit.py        # Monthly health check & contradiction detection
└── main.py             # CLI entry point for the user


## 4. Implementation Stages (Agent Task List)

### Stage 1: Infrastructure
- Configure `docker-compose.yml` to run Qdrant on port 6333.
- Initialize `vault/` and `wiki/` directories.

### Stage 2: Ingestion Pipeline (`scripts/ingest.py`)
- Implement file detection in `vault/`.
- Use **Docling** to extract text and structural metadata.
- Perform semantic chunking (Heading-aware).
- Upsert chunks into Qdrant with payload (filename, path, timestamp).

### Stage 3: Hybrid Search (`scripts/search.py`)
- Implement Qdrant hybrid search:
  - `dense_vector` (from local embedding model).
  - `full_text_search` (BM25) for keyword exact-matching.
- Implement a reranking layer to ensure top results are contextually relevant.

### Stage 4: Intelligence Layer (`scripts/router.py`)
- Create a router function:
  - **Mode A (Fast):** Use local Ollama for tagging/summaries.
  - **Mode B (Deep):** Fetch context, send to OpenRouter (Claude/Llama) for complex reasoning.

### Stage 5: User Interface (`main.py`)
- Create a CLI loop:
  - Input: `query`
  - Logic: Search -> Context Retrieval -> LLM Synthesis -> Output.
  - Display: Show answer + clickable citation source.

## 4.1 Development Workflow

Use the project workflow files for production development:

- `PREREQUISITES.md` explains required and optional local tools.
- `DEVELOPMENT.md` lists daily commands.
- `PROJECT_PLAN.md` tracks phase-by-phase production work.
- `RELEASE_CHECKLIST.md` defines the phase completion checklist.

Common commands:

```bash
make doctor
make test
make smoke
```

## 5. Operational Rules for the Agent
- **DO NOT** store API keys in the code (use `.env`).
- **DO** verify Qdrant is running before initiating any ingest script.
- **DO** ensure the local M4 GPU is utilized for embeddings (Ollama).
- **NEVER** hallucinate; if Qdrant returns 0 results, return "No information found in your knowledge base."

## 6. Self-Improvement Loop
- Implement `audit.py`: A routine that reads the `/wiki`, checks for stale content (older than 90 days), finds philosophical contradictions between notes, and suggests new article topics.

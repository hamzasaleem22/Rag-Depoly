# RAG Pipeline — Semantic Search Chatbot

A full-stack Retrieval-Augmented Generation (RAG) chatbot for question answering over **Microsoft's 2025 Annual Report**. The backend ingests a PDF (text + tables), builds a FAISS vector index, retrieves relevant chunks with MMR + cross-encoder reranking, and answers via LLM. The frontend is a dark-themed chat UI built with TanStack React.

## Architecture

```
                    ┌─────────────────────────┐
                    │   TanStack React UI     │
                    │   localhost:5173         │
                    └──────────┬──────────────┘
                               │ POST /query
                    ┌──────────▼──────────────┐
                    │   FastAPI Backend        │
                    │   localhost:8000          │
                    │                          │
                    │  ┌────────────────────┐  │
                    │  │  Retriever (MMR)   │  │
                    │  │  → Reranker (CE)   │  │
                    │  └────────┬───────────┘  │
                    │           │              │
                    │  ┌────────▼───────────┐  │
                    │  │  LLM (Gemini/OpenAI) │  │
                    │  └────────────────────┘  │
                    └──────────────────────────┘

PDF → Loader (PyMuPDF + Camelot) → Chunker → Embeddings → FAISS Index
```

## Features

**Backend:**
- PDF ingestion — text via PyMuPDF, tables via Camelot
- Semantic chunking with configurable size/overlap
- FAISS vector index with MMR retrieval
- Cross-Encoder reranking for precision
- Configurable LLM — Google Gemini or OpenAI/Codex
- Query caching (in-memory)
- FastAPI REST server with health, ingest, and query endpoints
- CLI with ingest, query, REPL, and server modes

**Frontend:**
- Dark-themed chat interface with aurora backdrop
- Suggest prompt cards for quick queries
- Markdown rendering with code highlighting
- Expandable source citations with page and content
- Typing indicator, timestamps, scroll-to-bottom

## Project Structure

```
Rag_Backend/
└── pipeline/
    ├── config.yaml              # Runtime configuration
    ├── .env                     # API keys (gitignored)
    ├── requirements.txt         # Python dependencies
    ├── pyproject.toml           # Project metadata
    └── src/
        ├── cli.py               # CLI entry point
        ├── config.py            # Config loader (Pydantic)
        ├── cache.py             # Query cache
        ├── pipeline.py          # Orchestrator
        ├── api/
        │   ├── models.py        # Pydantic schemas
        │   ├── routes.py        # FastAPI routes
        │   └── server.py        # FastAPI app
        ├── ingestion/
        │   ├── loader.py        # PDF loader (text + tables)
        │   ├── chunker.py       # Text splitter
        │   └── vectorstore.py   # FAISS index builder
        ├── retrieval/
        │   ├── embedder.py      # Embedding model
        │   ├── retriever.py     # MMR retriever
        │   └── reranker.py      # CrossEncoder reranker
        └── generation/
            ├── prompt.py        # Prompt templates
            └── llm.py           # LLM client

Rag_Frontend/
└── RagChatbot_Frontend/
    ├── package.json             # Node dependencies
    ├── vite.config.ts           # Vite + TanStack config
    ├── .env                     # VITE_CHAT_API_URL (gitignored)
    └── src/
        ├── styles.css           # Tailwind v4 + theme
        ├── lib/
        │   └── lovable-error-reporting.ts
        └── routes/
            ├── __root.tsx       # Root shell, head, links
            └── index.tsx        # Main chat page component
```

## Quick Start

### Backend

```bash
cd Rag_Backend/pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your GOOGLE_GEMINI_API_KEY and/or OPENAI_API_KEY

# Ingest the PDF
python3 -m src.cli --ingest

# Start the API server
python3 -m src.cli --server
```
cd Rag_Backend/pipeline
python3 -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000

The backend runs on `http://localhost:8000`.

### Frontend

```bash
cd Rag_Frontend/RagChatbot_Frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173`.

Set `VITE_CHAT_API_URL` in `.env` to point at your backend (e.g. `http://localhost:8000` or a ngrok URL).

## API Endpoints

| Method | Path       | Description                        |
|--------|------------|------------------------------------|
| GET    | `/health`  | Service health, chunks, cache      |
| POST   | `/ingest`  | Run ingestion pipeline             |
| POST   | `/query`   | Ask a question (returns answer + sources) |

**Query example:**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What was Microsoft'\''s total revenue in FY2025?"}'
```

Response:
```json
{
  "answer": "Microsoft's total revenue in FY2025 was **$281.724 billion**.",
  "sources": [
    {"page": 59, "type": "table", "content": "..."},
    {"page": 57, "type": "text", "content": "..."}
  ]
}
```

## CLI Usage

```bash
python3 -m src.cli --ingest                    # Ingest PDF → FAISS index
python3 -m src.cli --server                    # Start API server
python3 -m src.cli --query "Your question?"    # Run a query
python3 -m src.cli --repl                      # Interactive REPL
```

## Configuration

All settings in `Rag_Backend/pipeline/config.yaml`:

| Section     | Key               | Default                        |
|-------------|-------------------|--------------------------------|
| embeddings  | model             | `all-MiniLM-L6-v2`             |
| chunking    | chunk_size        | 1500                           |
| chunking    | chunk_overlap     | 250                            |
| retriever   | type / k / fetch_k| mmr / 10 / 20                  |
| reranker    | model / top_k     | `ms-marco-MiniLM-L6-v2` / 5   |
| llm         | provider / model  | google / `gemini-2.0-flash`    |
| cache       | backend / max_size| memory / 100                   |
| server      | host / port       | 0.0.0.0 / 8000                 |

## Running Both Services

```bash
# Terminal 1 — Backend
cd Rag_Backend/pipeline && python3 -m src.cli --server

# Terminal 2 — Frontend
cd Rag_Frontend/RagChatbot_Frontend && npm run dev
```

Open `http://localhost:5173` in your browser.

## Tech Stack

- **LangChain** — document loading, chunking, LLM integration
- **FAISS** — vector similarity search
- **Sentence-Transformers** — embeddings and cross-encoder reranking
- **PyMuPDF** — PDF text extraction
- **Camelot** — PDF table extraction
- **FastAPI + Uvicorn** — REST API
- **Google Gemini / OpenAI (Codex)** — LLM providers
- **TanStack Start + React** — frontend framework
- **Tailwind CSS v4** — styling
- **Vite** — build tool

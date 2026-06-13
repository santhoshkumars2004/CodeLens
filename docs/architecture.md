# StackSense — Architecture

## System Overview

StackSense is built on a **RAG (Retrieval Augmented Generation)** architecture that combines
vector similarity search with LLM-powered answer generation.

## Architecture Flow

```
┌─────────────────┐
│   User Browser   │
└────────┬────────┘
         │ HTTPS
┌────────▼────────┐
│  Next.js Frontend│──── Vercel / k8s
└────────┬────────┘
         │ REST API
┌────────▼────────┐
│ FastAPI Backend  │──── k8s / EC2
│                  │
│  ┌─── Ingest ──┐│      ┌────────────┐
│  │Clone → Parse ││      │  ChromaDB   │
│  │Chunk → Embed ││◄────►│ Vector DB   │
│  │Store         ││      └────────────┘
│  └──────────────┘│
│                  │      ┌────────────┐
│  ┌─── Query ───┐│      │ HuggingFace│
│  │Embed Query   ││◄────►│ Embeddings │
│  │Retrieve      ││      └────────────┘
│  │Rerank        ││
│  │Generate      ││      ┌────────────┐
│  └──────────────┘│◄────►│  Groq API  │
│                  │      │  (LLaMA3)  │
└──────────────────┘      └────────────┘
         │
┌────────▼────────┐
│   Prometheus     │
│   + Grafana      │
└─────────────────┘
```

## Data Flow

### Ingestion Pipeline
1. **Clone**: GitPython shallow-clones the repository
2. **Filter**: Skip binaries, node_modules, lock files, etc.
3. **Parse**: AST-based parsing for Python; regex for JS/TS
4. **Chunk**: Split code into semantic units (functions, classes)
5. **Embed**: Generate vectors via HuggingFace sentence-transformers
6. **Store**: Persist chunks + vectors in ChromaDB

### Query Pipeline
1. **Embed Query**: Same embedding model as ingestion
2. **Retrieve**: Top-K vector similarity search in ChromaDB
3. **Rerank**: Cross-encoder reranking for improved relevance
4. **Generate**: LLM (Groq LLaMA3) generates answer with citations
5. **Respond**: Structured JSON with answer + file:line citations

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vector DB | ChromaDB | Free, local, persistent, Python-native |
| Embeddings | all-MiniLM-L6-v2 | Fast, free, good code understanding |
| LLM | Groq LLaMA3-8b | 6000 free req/day, fast inference |
| Reranker | ms-marco-MiniLM | Cross-encoder for better relevance |
| Backend | FastAPI | Async, OpenAPI docs, Pydantic models |
| Frontend | Next.js 14 | App Router, SSR, great DX |
| Container | Docker + k8s | Industry standard, autoscaling |

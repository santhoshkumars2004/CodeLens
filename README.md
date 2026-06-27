# 🧠 CodeLens — AI Codebase Q&A

> Ask questions about any GitHub repository and get precise, cited answers with exact file and line references.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![LLaMA3](https://img.shields.io/badge/LLM-LLaMA3-purple)
![ChromaDB](https://img.shields.io/badge/VectorDB-ChromaDB-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 🚀 What is CodeLens?

CodeLens is an AI-powered codebase Q&A system that uses **RAG (Retrieval Augmented Generation)** to help developers understand any GitHub repository through natural language questions.

**How it works:**
1. Paste a GitHub repo URL
2. CodeLens clones, parses, and indexes the codebase
3. Ask questions like *"How does authentication work?"*
4. Get answers with **exact file:line citations**

## 🏗️ Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Backend | Python 3.11, FastAPI | Free |
| Vector DB | ChromaDB (local) | Free |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` | Free |
| LLM | Groq API (LLaMA3-8b) | Free |
| Frontend | Next.js 14, Tailwind CSS | Free |
| Monitoring | Prometheus + Grafana | Free |
| Containers | Docker + Kubernetes | Free |

## ⚡ Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git
- [Groq API Key](https://console.groq.com) (free)

### 1. Clone & Setup
```bash
git clone https://github.com/santhoshkumars2004/CodeLens.git
cd codelens
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Docker (Alternative)
```bash
docker-compose up --build
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ingest` | Index a GitHub repository |
| `POST` | `/api/query` | Ask a question about a repo |
| `GET` | `/api/repos` | List indexed repositories |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | Swagger API docs |

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

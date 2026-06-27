"""
scripts/test_chat.py — Interactive CLI to test the full CodeLens Backend RAG pipeline.

Run from backend/:
    python scripts/test_chat.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.query.pipeline import query_pipeline
from app.vectordb.vector_store import get_chroma_client

def get_latest_repo():
    client = get_chroma_client()
    cols = client.list_collections()
    if not cols:
        return None
    # pick the largest collection (the most recently indexed repo)
    best = max(cols, key=lambda c: client.get_collection(c.name).count())
    return best.name.replace("_", "/", 1)

def main():
    print("\n========================================================")
    print("🤖 CodeLens Backend — Interactive CLI Test")
    print("========================================================\n")
    
    repo_id = get_latest_repo()
    if not repo_id:
        print("❌ No repositories found in ChromaDB. Please ingest one first!")
        sys.exit(1)
        
    print(f"🎯 Defaulting to latest indexed repo: {repo_id}")
    print("Type 'exit' or 'quit' to stop.\n")
    
    while True:
        try:
            question = input("\n👤 Ask a question: ")
            if question.strip().lower() in ['exit', 'quit']:
                break
            if not question.strip():
                continue
                
            print(f"\n🧠 Thinking... (Searching ChromaDB + BM25, then asking Groq LLaMA3)")
            
            # Execute full pipeline
            result = query_pipeline(
                question=question,
                repo_id=repo_id,
                top_k=5
            )
            
            print("\n" + "="*50)
            print("🤖 CODELENS RESPONSE:")
            print("="*50 + "\n")
            
            print(result["answer"])
            
            print("\n" + "-"*50)
            print(f"Latency: {result['latency_ms']} ms | Confidence: {result['confidence_score']}")
            print("-"*50 + "\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error during query: {str(e)}")

if __name__ == "__main__":
    import logging
    # Suppress all the verbose info logs during the chat
    logging.getLogger("app").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    main()

"""
Test script to verify hybrid retrieval
"""
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.retrieval.retriever import retrieve
from app.utils.logger import setup_logging

def main():
    setup_logging("DEBUG")
    repo_id = "santhoshkumars2004/CodeLens"
    
    print("Testing Conceptual Query (Dense Should Shine)")
    res = retrieve("how does login and authentication work?", repo_id, top_k=5)
    for r in res:
        print(f"[{r['relevance_score']}] {r['metadata']['file_path']} - {r['metadata'].get('name', 'N/A')}")
        
    print("\n---------------------------\n")
    
    print("Testing Keyword Query (BM25 Should Shine)")
    res2 = retrieve("clone_repository", repo_id, top_k=5)
    for r in res2:
        print(f"[{r.get('relevance_score', 'N/A')}] {r['metadata']['file_path']} - {r['metadata'].get('name', 'N/A')}")

if __name__ == "__main__":
    main()

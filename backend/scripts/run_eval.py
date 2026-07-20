"""
CodeLens — RAG Evaluation Script (scripts/run_eval.py)

Measures two independent scores for the RAG pipeline:
  1. CITATION ACCURACY — Did it retrieve the correct file?
  2. ANSWER QUALITY    — Did the answer mention the expected keywords?

These can and do diverge:
  Citation 40% + Answer 80%  → RAG is hallucinating from wrong context (DANGEROUS)
  Citation 80% + Answer 40%  → Retrieval works, improve the LLM prompt
  Both high                  → Production ready ✅
  Both low                   → Fix chunking / embedding / retrieval

Usage:
    cd backend
    python -m scripts.run_eval --repo-id <owner/repo>

    # Example (run against locally-indexed CodeLens repo):
    python -m scripts.run_eval --repo-id santhoshkumars2004/CodeLens

Requirements:
    - The repository must already be indexed (POST /api/ingest called first)
    - The backend must be running:
        uvicorn main:app --reload
    OR via Docker:
        docker-compose up --build
"""

import asyncio
import json
import argparse
import sys
import os
from pathlib import Path
from typing import Any

# ── Path setup ──────────────────────────────────────────────────────────
# Allow running as `python -m scripts.run_eval` from /backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set minimal env for import
os.environ.setdefault("EMBEDDING_MODEL", "fastembed/BAAI/bge-small-en-v1.5")
os.environ.setdefault("CHROMA_PERSIST_DIR", "./data/chromadb")

from app.query.pipeline import query_pipeline

# ── Config ───────────────────────────────────────────────────────────────
EVAL_SET_PATH = Path(__file__).parent.parent / "tests" / "eval_set.json"

# Scoring thresholds — what we consider "production ready"
CITATION_PASS_THRESHOLD = 0.75   # 75% correct file citations
ANSWER_PASS_THRESHOLD   = 0.70   # 70% answers contain expected keywords


# ── Colors for terminal output ────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def check_citation_accuracy(result: dict[str, Any], test: dict) -> tuple[bool, str]:
    """
    Check if the top citation points to the expected file.
    Returns (passed, reason).
    """
    citations = result.get("citations", [])
    if not citations:
        return False, "No citations returned"

    expected_file = test["expected_file"]
    expected_start, expected_end = test["expected_lines"]

    # Check if any citation matches the expected file
    for citation in citations[:3]:  # Check top 3
        cited_file = citation.get("file_path", "")
        # Normalize paths for comparison
        if expected_file.replace("\\", "/").split("/")[-1] in cited_file:
            cited_start = citation.get("start_line", 0)
            # Line must be within ±20 lines of expected range
            if abs(cited_start - expected_start) <= 20:
                return True, f"✅ Correct file + line ({cited_file}:{cited_start})"
            else:
                return False, f"⚠️  Correct file, wrong line (got {cited_start}, expected ~{expected_start})"

    top_file = citations[0].get("file_path", "unknown")
    return False, f"❌ Wrong file (got {top_file}, expected {expected_file})"


def check_answer_quality(result: dict[str, Any], test: dict) -> tuple[bool, str]:
    """
    Check if the answer contains expected keywords.
    Returns (passed, reason).
    """
    answer = result.get("answer", "").lower()
    keywords = test.get("expected_keywords", [])

    if not keywords:
        return True, "No keywords to check"

    matched = [kw for kw in keywords if kw.lower() in answer]
    score = len(matched) / len(keywords)

    if score >= 0.5:  # At least half the keywords present
        return True, f"✅ {len(matched)}/{len(keywords)} keywords found: {matched[:3]}"
    else:
        missing = [kw for kw in keywords if kw.lower() not in answer]
        return False, f"❌ Only {len(matched)}/{len(keywords)} keywords. Missing: {missing[:3]}"


async def run_single_test(test: dict, repo_id: str, verbose: bool = True) -> dict:
    """Run a single eval test case and return results."""
    try:
        result = await query_pipeline(
            question=test["question"],
            repo_id=repo_id,
            top_k=5,
        )
    except Exception as e:
        return {
            "id": test["id"],
            "question": test["question"],
            "citation_pass": False,
            "answer_pass": False,
            "citation_reason": f"ERROR: {e}",
            "answer_reason": f"ERROR: {e}",
            "latency_ms": 0,
        }

    citation_pass, citation_reason = check_citation_accuracy(result, test)
    answer_pass, answer_quality = check_answer_quality(result, test)

    if verbose:
        status = GREEN + "PASS" + RESET if (citation_pass and answer_pass) else RED + "FAIL" + RESET
        print(f"\n  [{test['id']}] {status}")
        print(f"  Q: {test['question'][:80]}...")
        print(f"  Citation: {citation_reason}")
        print(f"  Answer:   {answer_quality}")
        print(f"  Latency:  {result.get('latency_ms', 0):.0f}ms")

    return {
        "id": test["id"],
        "question": test["question"],
        "citation_pass": citation_pass,
        "answer_pass": answer_pass,
        "citation_reason": citation_reason,
        "answer_reason": answer_quality,
        "latency_ms": result.get("latency_ms", 0),
        "answer_snippet": result.get("answer", "")[:200],
    }


async def run_eval(repo_id: str, filter_group: str | None = None, verbose: bool = True):
    """Run the full evaluation suite against a repository."""

    eval_set = json.loads(EVAL_SET_PATH.read_text())

    # Filter out comment-only entries
    tests = [t for t in eval_set if "question" in t]

    # Optionally filter by group prefix (e.g., "vs", "emb", "ff")
    if filter_group:
        tests = [t for t in tests if t["id"].startswith(filter_group)]
        print(f"{CYAN}Filtering to group '{filter_group}' → {len(tests)} tests{RESET}")

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  CodeLens RAG Evaluation{RESET}")
    print(f"  Repo:  {repo_id}")
    print(f"  Tests: {len(tests)}")
    print(f"{BOLD}{'='*60}{RESET}")

    results = []
    for i, test in enumerate(tests, 1):
        print(f"\n{CYAN}[{i}/{len(tests)}]{RESET}", end="")
        result = await run_single_test(test, repo_id, verbose=verbose)
        results.append(result)

    # ── Final scores ─────────────────────────────────────────────────────
    total = len(results)
    citation_hits = sum(1 for r in results if r["citation_pass"])
    answer_hits   = sum(1 for r in results if r["answer_pass"])
    both_pass     = sum(1 for r in results if r["citation_pass"] and r["answer_pass"])
    avg_latency   = sum(r["latency_ms"] for r in results) / max(total, 1)

    citation_pct = citation_hits / total * 100
    answer_pct   = answer_hits   / total * 100
    both_pct     = both_pass     / total * 100

    citation_color = GREEN if citation_hits / total >= CITATION_PASS_THRESHOLD else RED
    answer_color   = GREEN if answer_hits   / total >= ANSWER_PASS_THRESHOLD   else RED

    print(f"\n\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  RESULTS SUMMARY{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Total tests     : {total}")
    print(f"  Citation Accuracy: {citation_color}{citation_hits}/{total} = {citation_pct:.1f}%{RESET}  (target ≥ {CITATION_PASS_THRESHOLD*100:.0f}%)")
    print(f"  Answer Quality   : {answer_color}{answer_hits}/{total} = {answer_pct:.1f}%{RESET}  (target ≥ {ANSWER_PASS_THRESHOLD*100:.0f}%)")
    print(f"  Both Pass        : {both_pass}/{total} = {both_pct:.1f}%")
    print(f"  Avg Latency      : {avg_latency:.0f}ms")
    print(f"{BOLD}{'='*60}{RESET}")

    # ── Diagnosis ────────────────────────────────────────────────────────
    print(f"\n{BOLD}DIAGNOSIS:{RESET}")
    if citation_pct < 50 and answer_pct >= 70:
        print(f"  {RED}⚠️  HALLUCINATION RISK: Good-sounding answers from wrong files!{RESET}")
        print(f"     → Fix chunking strategy or embedding model")
    elif citation_pct >= 75 and answer_pct < 70:
        print(f"  {YELLOW}⚠️  PROMPT ISSUE: Right files found, but weak explanations.{RESET}")
        print(f"     → Improve the LLM system prompt in app/llm/generator.py")
    elif citation_pct < 50 and answer_pct < 50:
        print(f"  {RED}❌ RETRIEVAL BROKEN: Both citation and answer failing.{RESET}")
        print(f"     → Check embeddings, chunking, and ChromaDB indexing")
    elif citation_pct >= 75 and answer_pct >= 70:
        print(f"  {GREEN}✅ PRODUCTION READY: Both scores above threshold!{RESET}")
    else:
        print(f"  {YELLOW}⚠️  PARTIAL: Some areas need improvement (see failed tests above){RESET}")

    # ── Failed tests ─────────────────────────────────────────────────────
    failed = [r for r in results if not r["citation_pass"] or not r["answer_pass"]]
    if failed:
        print(f"\n{BOLD}FAILED TESTS:{RESET}")
        for r in failed:
            flags = []
            if not r["citation_pass"]: flags.append("citation")
            if not r["answer_pass"]:   flags.append("answer")
            print(f"  [{r['id']}] Failed: {', '.join(flags)}")
            print(f"    Q: {r['question'][:70]}...")

    # Save results to file
    output_path = Path("tests/eval_results.json")
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(json.dumps({
        "repo_id": repo_id,
        "total": total,
        "citation_accuracy_pct": round(citation_pct, 1),
        "answer_quality_pct": round(answer_pct, 1),
        "avg_latency_ms": round(avg_latency, 0),
        "results": results,
    }, indent=2))
    print(f"\n  📄 Full results saved to: {output_path}")

    return citation_pct, answer_pct


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CodeLens RAG evaluation")
    parser.add_argument(
        "--repo-id",
        required=True,
        help="Repository ID to test against (e.g. santhoshkumars2004/CodeLens)"
    )
    parser.add_argument(
        "--group",
        default=None,
        help="Filter tests by group prefix: vs, emb, ff, ing, cl, qp, rr, api, cfg"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show summary, not per-test details"
    )
    args = parser.parse_args()

    asyncio.run(run_eval(
        repo_id=args.repo_id,
        filter_group=args.group,
        verbose=not args.quiet,
    ))

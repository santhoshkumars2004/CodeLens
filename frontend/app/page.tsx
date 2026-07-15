"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { SignInButton, SignedIn, SignedOut, UserButton, useAuth } from '@clerk/nextjs'
import RepoInput from "@/components/RepoInput";
import IndexingProgress from "@/components/IndexingProgress";
import { ingestRepo, listRepos, getIngestStatus, deleteRepo } from "@/lib/api";
import type { RepoInfo, IngestResponse, IngestStatus } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [isIngesting, setIsIngesting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [error, setError] = useState("");
  const [result, setResult] = useState<IngestResponse | null>(null);

  // Fetch existing indexed repos
  const fetchRepos = () => {
    listRepos()
      .then((data) => setRepos(data.repos))
      .catch(() => {});
  };

  useEffect(() => {
    fetchRepos();
  }, []);

  const handleDelete = async (e: React.MouseEvent, repoId: string) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete ${repoId}?`)) return;
    try {
      await deleteRepo(repoId);
      // Remove from state immediately for snappy UI
      setRepos((prev) => prev.filter((r) => r.repo_id !== repoId));
    } catch (err) {
      alert("Failed to delete repository");
    }
  };

  const handleIngest = async (url: string) => {
    setIsIngesting(true);
    setError("");
    setResult(null);
    setProgress(10);
    setStatusMessage("Starting ingestion...");

    try {
      const token = await getToken();
      if (!token) {
        throw new Error("You must be logged in to index repositories.");
      }
      const response = await ingestRepo(url, undefined, token);
      
      // Poll for status
      const repoId = response.repo_id;
      
      const pollInterval = setInterval(async () => {
        try {
          const statusData = await getIngestStatus(repoId);
          setProgress(statusData.progress);
          setStatusMessage(statusData.message);
          
          if (statusData.status === "completed") {
            clearInterval(pollInterval);
            setProgress(100);
            setStatusMessage("Repository indexed successfully!");
            setResult({
              ...response,
              status: "completed",
              message: "Repository indexed successfully!"
            });

            // Refresh repos list
            const reposData = await listRepos();
            setRepos(reposData.repos);

            // Navigate to chat after short delay
            setTimeout(() => {
              router.push(`/chat/${encodeURIComponent(repoId)}`);
            }, 1500);
          } else if (statusData.status === "error") {
            clearInterval(pollInterval);
            setProgress(0);
            setError(statusData.message || "Ingestion failed");
            setIsIngesting(false);
          }
        } catch (pollErr) {
          // Keep polling even if one request fails
          console.error("Poll error:", pollErr);
        }
      }, 2000);
      
    } catch (err) {
      setProgress(0);
      setError(err instanceof Error ? err.message : "Ingestion failed");
      setIsIngesting(false);
    }
  };

  return (
    <main className="min-h-screen flex flex-col">
      {/* Navigation */}
      <nav className="border-b border-[var(--color-border)] px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center text-sm font-bold">
              S
            </div>
            <span className="text-lg font-semibold">CodeLens</span>
          </div>
          <div className="flex items-center gap-4">
            <SignedOut>
              <div className="btn-glow text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity">
                <SignInButton />
              </div>
            </SignedOut>
            <SignedIn>
              <UserButton />
            </SignedIn>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-20">
        {/* Background gradient orbs */}
        <div className="fixed inset-0 pointer-events-none overflow-hidden">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#6366f1] rounded-full opacity-5 blur-[120px]" />
          <div className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-[#a855f7] rounded-full opacity-5 blur-[100px]" />
          <div className="absolute top-1/2 right-1/3 w-64 h-64 bg-[#06b6d4] rounded-full opacity-3 blur-[80px]" />
        </div>

        <div className="relative z-10 text-center mb-12 animate-fade-in-up">
          <div className="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 text-xs text-[var(--color-text-muted)] mb-6">
            <span className="w-1.5 h-1.5 bg-[var(--color-success)] rounded-full animate-pulse" />
            Powered by RAG + LLaMA3
          </div>

          <h1 className="text-5xl md:text-6xl font-bold mb-4 tracking-tight">
            <span className="gradient-text">Understand</span> any codebase
            <br />
            in seconds
          </h1>

          <p className="text-lg text-[var(--color-text-secondary)] max-w-xl mx-auto">
            Paste a GitHub repo URL. Ask questions in plain English.
            Get answers with{" "}
            <span className="text-[var(--color-accent)]">
              exact file:line citations
            </span>
            .
          </p>
        </div>

        {/* Repo Input */}
        <div
          className="relative z-10 w-full animate-fade-in-up"
          style={{ animationDelay: "200ms" }}
        >
          <RepoInput onSubmit={handleIngest} isLoading={isIngesting} />
        </div>

        {/* Progress */}
        {isIngesting && (
          <IndexingProgress
            progress={Math.round(progress)}
            status="indexing"
            message={statusMessage}
          />
        )}

        {/* Success result */}
        {result && (
          <div className="mt-6 glass rounded-xl p-6 max-w-xl w-full text-center animate-fade-in-up">
            <div className="text-2xl mb-2">✅</div>
            <p className="text-[var(--color-success)] font-medium">
              {result.message}
            </p>
            <div className="flex justify-center gap-6 mt-3 text-sm text-[var(--color-text-muted)]">
              <span>{result.files_indexed} files</span>
              <span>{result.chunks_created} chunks</span>
              <span>{result.duration_seconds}s</span>
            </div>
            <p className="text-xs text-[var(--color-text-muted)] mt-2">
              Redirecting to chat...
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-6 glass rounded-xl p-4 max-w-xl w-full text-center border border-[var(--color-error)]/30 animate-fade-in-up">
            <p className="text-[var(--color-error)] text-sm">❌ {error}</p>
          </div>
        )}

        {/* Indexed Repos */}
        {repos.length > 0 && !isIngesting && (
          <div
            className="mt-16 w-full max-w-2xl animate-fade-in-up"
            style={{ animationDelay: "400ms" }}
          >
            <h2 className="text-sm font-medium text-[var(--color-text-muted)] mb-4 text-center">
              Indexed Repositories
            </h2>
            <div className="grid gap-3">
              {repos.map((repo) => (
                <div
                  key={repo.repo_id}
                  id={`repo-${repo.repo_id.replace("/", "-")}`}
                  className="glass glass-hover rounded-xl p-4 text-left transition-all group flex items-center justify-between cursor-pointer"
                  onClick={() => router.push(`/chat/${encodeURIComponent(repo.repo_id)}`)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[var(--color-bg-tertiary)] flex items-center justify-center text-sm">
                      📦
                    </div>
                    <div>
                      <p className="font-medium text-sm group-hover:text-[var(--color-accent)] transition-colors">
                        {repo.repo_id}
                      </p>
                      <p className="text-xs text-[var(--color-text-muted)]">
                        {repo.chunks_count} chunks indexed
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => handleDelete(e, repo.repo_id)}
                      className="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-error)] hover:bg-[var(--color-bg-tertiary)] transition-all opacity-0 group-hover:opacity-100"
                      title="Delete repository"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14H6L5 6" />
                        <path d="M10 11v6M14 11v6" />
                        <path d="M9 6V4h6v2" />
                      </svg>
                    </button>
                    <svg
                      className="w-4 h-4 text-[var(--color-text-muted)] group-hover:text-[var(--color-accent)] transition-all group-hover:translate-x-1"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Feature cards */}
        {!isIngesting && !result && (
          <div
            className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl w-full animate-fade-in-up"
            style={{ animationDelay: "600ms" }}
          >
            {[
              {
                icon: "🔍",
                title: "Semantic Search",
                desc: "Understands meaning, not just keywords. Find code by intent.",
              },
              {
                icon: "📍",
                title: "Exact Citations",
                desc: "Every answer includes file paths and line numbers.",
              },
              {
                icon: "⚡",
                title: "Lightning Fast",
                desc: "Powered by Groq's LLaMA3 — answers in under 3 seconds.",
              },
            ].map((feature) => (
              <div
                key={feature.title}
                className="glass rounded-xl p-5 hover:border-[var(--color-border-active)] transition-all group"
              >
                <div className="text-2xl mb-3">{feature.icon}</div>
                <h3 className="font-medium text-sm mb-1">{feature.title}</h3>
                <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">
                  {feature.desc}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-[var(--color-text-muted)]">
          <span>CodeLens v1.0.0</span>
          <span>RAG + ChromaDB + LLaMA3</span>
        </div>
      </footer>
    </main>
  );
}

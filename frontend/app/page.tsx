"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { SignInButton, UserButton, useAuth } from "@clerk/nextjs";
import RepoInput from "@/components/RepoInput";
import IndexingProgress from "@/components/IndexingProgress";
import { ingestRepo, listRepos, getIngestStatus, deleteRepo } from "@/lib/api";
import type { RepoInfo, IngestResponse } from "@/lib/types";

// ─── Landing Page (unauthenticated) ─────────────────────────────────────────
function LandingPage() {
  return (
    <main className="min-h-screen flex flex-col bg-[#080810]">
      {/* Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-20%] left-[10%] w-[600px] h-[600px] bg-[#6366f1] rounded-full opacity-[0.06] blur-[140px]" />
        <div className="absolute bottom-[-10%] right-[5%] w-[500px] h-[500px] bg-[#a855f7] rounded-full opacity-[0.06] blur-[120px]" />
        <div className="absolute top-[50%] left-[50%] w-[300px] h-[300px] bg-[#06b6d4] rounded-full opacity-[0.04] blur-[100px]" />
        {/* Grid lines */}
        <div className="absolute inset-0" style={{
          backgroundImage: "linear-gradient(rgba(99,102,241,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.04) 1px, transparent 1px)",
          backgroundSize: "60px 60px"
        }} />
      </div>

      {/* Navbar */}
      <nav className="relative z-10 px-6 py-5 flex items-center justify-between max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center shadow-lg shadow-[#6366f1]/20">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </div>
          <span className="text-xl font-bold tracking-tight">CodeLens</span>
        </div>
        <div className="flex items-center gap-4">
          <a href="https://github.com/santhoshkumars2004/CodeLens" target="_blank" className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1.5">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
            GitHub
          </a>
          <div className="h-4 w-px bg-white/10" />
          <div className="text-sm font-medium text-white bg-gradient-to-r from-[#6366f1] to-[#a855f7] px-5 py-2 rounded-full cursor-pointer hover:opacity-90 transition-all hover:shadow-lg hover:shadow-[#6366f1]/30">
            <SignInButton>Get Started Free</SignInButton>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 pt-16 pb-24 text-center">
        <div className="inline-flex items-center gap-2 border border-[#6366f1]/30 bg-[#6366f1]/10 rounded-full px-4 py-1.5 text-xs text-[#a5b4fc] mb-8 backdrop-blur-sm">
          <span className="w-1.5 h-1.5 bg-[#6366f1] rounded-full animate-pulse" />
          RAG · HuggingFace Embeddings · LLaMA3 · ChromaDB
        </div>

        <h1 className="text-6xl md:text-7xl font-extrabold tracking-tight mb-6 max-w-4xl leading-[1.05]">
          <span style={{background: "linear-gradient(135deg, #fff 0%, #a5b4fc 50%, #c084fc 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent"}}>
            Your AI copilot
          </span>
          <br />
          <span className="text-white">for any codebase</span>
        </h1>

        <p className="text-lg text-gray-400 max-w-xl mb-10 leading-relaxed">
          Paste a GitHub URL. Ask questions in plain English.
          Get instant answers with <span className="text-[#a5b4fc] font-medium">exact file & line citations</span> — powered by semantic search.
        </p>

        {/* CTA */}
        <div className="flex flex-col sm:flex-row items-center gap-4 mb-20">
          <div className="relative group cursor-pointer">
            <div className="absolute inset-0 bg-gradient-to-r from-[#6366f1] to-[#a855f7] rounded-xl blur-lg opacity-50 group-hover:opacity-80 transition-all duration-300" />
            <div className="relative text-white font-semibold text-base px-8 py-3.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#a855f7] hover:shadow-2xl transition-all">
              <SignInButton>
                <span className="flex items-center gap-2">
                  Start Exploring Free
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </span>
              </SignInButton>
            </div>
          </div>
          <span className="text-xs text-gray-500">No credit card required</span>
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-4xl w-full">
          {[
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" strokeWidth="1.8"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
              ),
              title: "Semantic Search",
              desc: "Finds code by meaning, not keywords. Understands context and intent across your entire repository.",
              color: "#6366f1"
            },
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#c084fc" strokeWidth="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
              ),
              title: "Precise Citations",
              desc: "Every answer includes exact file paths and line numbers so you can jump to the code instantly.",
              color: "#a855f7"
            },
            {
              icon: (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#67e8f9" strokeWidth="1.8"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              ),
              title: "Sub-3s Answers",
              desc: "Powered by Groq's LLaMA3 inference. Parallel retrieval with RRF fusion for maximum accuracy.",
              color: "#06b6d4"
            }
          ].map((f) => (
            <div key={f.title} className="group relative text-left p-6 rounded-2xl border border-white/5 bg-white/[0.03] hover:border-white/10 hover:bg-white/[0.06] transition-all duration-300 backdrop-blur-sm">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style={{background: `${f.color}15`, border: `1px solid ${f.color}30`}}>
                {f.icon}
              </div>
              <h3 className="font-semibold text-white text-sm mb-2">{f.title}</h3>
              <p className="text-xs text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-600">
          <span>© 2025 CodeLens</span>
          <span>Built with RAG · ChromaDB · LLaMA3</span>
        </div>
      </footer>
    </main>
  );
}

// ─── App Dashboard (authenticated) ──────────────────────────────────────────
function AppDashboard() {
  const router = useRouter();
  const { getToken } = useAuth();
  const [isIngesting, setIsIngesting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("");
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [error, setError] = useState("");
  const [result, setResult] = useState<IngestResponse | null>(null);

  const fetchRepos = () => {
    listRepos().then((data) => setRepos(data.repos)).catch(() => {});
  };

  useEffect(() => { fetchRepos(); }, []);

  const handleDelete = async (e: React.MouseEvent, repoId: string) => {
    e.stopPropagation();
    if (!confirm(`Delete ${repoId}?`)) return;
    try {
      await deleteRepo(repoId);
      setRepos((prev) => prev.filter((r) => r.repo_id !== repoId));
    } catch { alert("Failed to delete repository"); }
  };

  const handleIngest = async (url: string) => {
    setIsIngesting(true);
    setError("");
    setResult(null);
    setProgress(10);
    setStatusMessage("Starting ingestion...");

    try {
      const token = await getToken();
      if (!token) throw new Error("You must be logged in to index repositories.");
      const response = await ingestRepo(url, undefined, token);
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
            setResult({ ...response, status: "completed", message: "Repository indexed successfully!" });
            const reposData = await listRepos();
            setRepos(reposData.repos);
            setTimeout(() => router.push(`/chat/${encodeURIComponent(repoId)}`), 1500);
          } else if (statusData.status === "error") {
            clearInterval(pollInterval);
            setProgress(0);
            setError(statusData.message || "Ingestion failed");
            setIsIngesting(false);
          }
        } catch (pollErr: any) { 
          if (pollErr.message && (pollErr.message.includes("404") || pollErr.message.includes("Failed to get status"))) {
            clearInterval(pollInterval);
            setProgress(0);
            setError("Ingestion failed: Backend restarted. Please try again in a few seconds.");
            setIsIngesting(false);
          }
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
      {/* Background orbs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#6366f1] rounded-full opacity-5 blur-[120px]" />
        <div className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-[#a855f7] rounded-full opacity-5 blur-[100px]" />
      </div>

      {/* Nav */}
      <nav className="border-b border-[var(--color-border)] px-6 py-4 relative z-10">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center shadow-md shadow-[#6366f1]/20">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <span className="text-lg font-bold">CodeLens</span>
          </div>
          <UserButton />
        </div>
      </nav>

      {/* Content */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-20 relative z-10">
        <div className="text-center mb-12 animate-fade-in-up">
          <h1 className="text-4xl md:text-5xl font-extrabold mb-4 tracking-tight">
            <span className="gradient-text">Index a Repository</span>
          </h1>
          <p className="text-[var(--color-text-secondary)] text-base max-w-md mx-auto">
            Paste any public GitHub URL to start chatting with that codebase.
          </p>
        </div>

        <div className="relative z-10 w-full animate-fade-in-up" style={{ animationDelay: "100ms" }}>
          <RepoInput onSubmit={handleIngest} isLoading={isIngesting} />
        </div>

        {isIngesting && (
          <IndexingProgress progress={Math.round(progress)} status="indexing" message={statusMessage} />
        )}

        {result && (
          <div className="mt-6 glass rounded-xl p-6 max-w-xl w-full text-center animate-fade-in-up">
            <div className="text-2xl mb-2">✅</div>
            <p className="text-[var(--color-success)] font-medium">{result.message}</p>
            <div className="flex justify-center gap-6 mt-3 text-sm text-[var(--color-text-muted)]">
              <span>{result.files_indexed} files</span>
              <span>{result.chunks_created} chunks</span>
              <span>{result.duration_seconds}s</span>
            </div>
            <p className="text-xs text-[var(--color-text-muted)] mt-2">Redirecting to chat...</p>
          </div>
        )}

        {error && (
          <div className="mt-6 glass rounded-xl p-4 max-w-xl w-full text-center border border-[var(--color-error)]/30 animate-fade-in-up">
            <p className="text-[var(--color-error)] text-sm">❌ {error}</p>
          </div>
        )}

        {/* Indexed Repos */}
        {repos.length > 0 && !isIngesting && (
          <div className="mt-14 w-full max-w-2xl animate-fade-in-up" style={{ animationDelay: "200ms" }}>
            <h2 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-widest mb-4 text-center">
              Your Indexed Repositories
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
                    <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#6366f1]/20 to-[#a855f7]/20 flex items-center justify-center border border-[#6366f1]/20">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a5b4fc" strokeWidth="2">
                        <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
                      </svg>
                    </div>
                    <div>
                      <p className="font-semibold text-sm group-hover:text-[var(--color-accent)] transition-colors">
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
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
                      </svg>
                    </button>
                    <svg className="w-4 h-4 text-[var(--color-text-muted)] group-hover:text-[var(--color-accent)] transition-all group-hover:translate-x-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/>
                    </svg>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <footer className="border-t border-[var(--color-border)] px-6 py-4 relative z-10">
        <div className="max-w-6xl mx-auto flex items-center justify-between text-xs text-[var(--color-text-muted)]">
          <span>CodeLens v1.0.0</span>
          <span>RAG · ChromaDB · LLaMA3</span>
        </div>
      </footer>
    </main>
  );
}

// ─── Root — Gate by auth ─────────────────────────────────────────────────────
export default function HomePage() {
  const { userId, isLoaded } = useAuth();

  if (!isLoaded) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#080810]">
        <div className="w-8 h-8 border-2 border-[#6366f1] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return userId ? <AppDashboard /> : <LandingPage />;
}

"use client";

import React, { useState } from "react";

interface RepoInputProps {
  onSubmit: (url: string) => void;
  isLoading: boolean;
}

export default function RepoInput({ onSubmit, isLoading }: RepoInputProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const validateUrl = (input: string) => {
    const pattern = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/;
    return pattern.test(input.trim());
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!url.trim()) {
      setError("Please enter a GitHub repository URL");
      return;
    }

    if (!validateUrl(url)) {
      setError("Please enter a valid GitHub URL (e.g., https://github.com/owner/repo)");
      return;
    }

    onSubmit(url.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="relative group">
        {/* Glow border effect */}
        <div className="absolute -inset-0.5 bg-gradient-to-r from-[#6366f1] via-[#a855f7] to-[#06b6d4] rounded-xl opacity-20 group-hover:opacity-40 blur transition-opacity duration-300" />

        <div className="relative glass rounded-xl p-1.5">
          <div className="flex items-center gap-2">
            {/* GitHub icon */}
            <div className="pl-4 text-[var(--color-text-muted)]">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </div>

            <input
              id="repo-url-input"
              type="url"
              value={url}
              onChange={(e) => { setUrl(e.target.value); setError(""); }}
              placeholder="https://github.com/owner/repository"
              className="flex-1 bg-transparent text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none py-3 px-2 text-base font-light"
              disabled={isLoading}
            />

            <button
              id="index-repo-btn"
              type="submit"
              disabled={isLoading || !url.trim()}
              className="btn-glow text-white px-6 py-2.5 rounded-lg font-medium text-sm disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 shrink-0"
            >
              {isLoading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Indexing...
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="16 16 12 12 8 16" />
                    <line x1="12" y1="12" x2="12" y2="21" />
                    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
                  </svg>
                  Index Repository
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <p className="mt-3 text-[var(--color-error)] text-sm text-center animate-fade-in-up">
          {error}
        </p>
      )}
    </form>
  );
}

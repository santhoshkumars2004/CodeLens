"use client";

import React, { useState } from "react";
import type { Citation } from "@/lib/types";

interface CitationCardProps {
  citation: Citation;
  index: number;
  repoUrl?: string;
}

export default function CitationCard({
  citation,
  index,
  repoUrl,
}: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  const githubUrl = repoUrl
    ? `${repoUrl}/blob/main/${citation.file_path}#L${citation.start_line}-L${citation.end_line}`
    : "#";

  const scoreColor =
    citation.relevance_score > 0.7
      ? "text-[var(--color-success)]"
      : citation.relevance_score > 0.4
      ? "text-[var(--color-warning)]"
      : "text-[var(--color-text-muted)]";

  return (
    <div
      className="citation-card p-3 animate-slide-in"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm hover:text-[var(--color-accent)] transition-colors"
        >
          <span className="text-[var(--color-accent)]">📄</span>
          <span className="font-mono text-xs text-[var(--color-text-primary)]">
            {citation.file_path}
          </span>
          <span className="text-[var(--color-text-muted)] text-xs">
            Lines {citation.start_line}-{citation.end_line}
          </span>
          <svg
            className={`w-3 h-3 transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>

        <div className="flex items-center gap-3">
          <span className={`text-xs font-mono ${scoreColor}`}>
            {Math.round(citation.relevance_score * 100)}%
          </span>
          {repoUrl && (
            <a
              href={githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
            >
              View in GitHub ↗
            </a>
          )}
        </div>
      </div>

      {/* Expandable code preview */}
      {expanded && (
        <div className="mt-3 code-block animate-fade-in-up">
          <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)]">
            <span className="text-xs text-[var(--color-text-muted)]">
              {citation.language}
            </span>
            <span className="text-xs text-[var(--color-text-muted)]">
              L{citation.start_line}–{citation.end_line}
            </span>
          </div>
          <pre className="p-4 text-xs leading-relaxed overflow-x-auto">
            <code>{citation.content}</code>
          </pre>
        </div>
      )}
    </div>
  );
}

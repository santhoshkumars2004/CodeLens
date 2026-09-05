"use client";

import React, { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Citation } from "@/lib/types";

interface CitationCardProps {
  citation: Citation;
  index: number;
  repoUrl?: string;
}

/**
 * Strip the chunk metadata header lines injected by the chunker.
 * The chunker prepends lines like:
 *   File: path/to/file.py
 *   Language: python
 *   Function: my_func
 *   Source: path/to/file.py
 * These are useful for the LLM but should never be visible to the user.
 */
function cleanContent(raw: string): string {
  const metaPattern = /^(File|Language|Function|Class|Module|Source|Type|Chunk)\s*:\s*.+$/;
  const lines = raw.split("\n");
  let startIdx = 0;
  for (let i = 0; i < lines.length; i++) {
    if (metaPattern.test(lines[i].trim())) {
      startIdx = i + 1;
    } else {
      break; // first non-meta line — everything after is real code
    }
  }
  return lines.slice(startIdx).join("\n").trimStart();
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

  const scoreLabel = (() => {
    const pct = Math.round(citation.relevance_score * 100);
    if (pct >= 70) return `${pct}% match — highly relevant`;
    if (pct >= 40) return `${pct}% match — partially relevant`;
    return `${pct}% match — low relevance`;
  })();

  const cleanCode = cleanContent(citation.content);

  return (
    <div
      className="citation-card p-3 animate-slide-in"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm hover:text-[var(--color-accent)] transition-colors min-w-0"
        >
          <span className="text-[var(--color-accent)] shrink-0">📄</span>
          <span className="font-mono text-xs text-[var(--color-text-primary)] truncate">
            {citation.file_path}
          </span>
          <span className="text-[var(--color-text-muted)] text-xs shrink-0">
            Lines {citation.start_line}–{citation.end_line}
          </span>
          <svg
            className={`w-3 h-3 shrink-0 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <div className="flex items-center gap-3 shrink-0 ml-2">
          <span
            className={`text-xs font-mono ${scoreColor} cursor-help`}
            title={`Relevance score: ${scoreLabel}\nScored by a cross-encoder AI model.`}
          >
            {Math.round(citation.relevance_score * 100)}% relevance
          </span>
          {repoUrl && (
            <a
              href={githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors whitespace-nowrap"
            >
              View in GitHub ↗
            </a>
          )}
        </div>
      </div>

      {/* Expanded code block — clean, no metadata headers */}
      {expanded && (
        <div className="mt-3 rounded-xl overflow-hidden border border-[var(--color-border)] animate-fade-in-up">
          {/* Top bar */}
          <div className="flex items-center justify-between px-4 py-2 bg-[#1e1e1e] border-b border-[var(--color-border)]">
            <span className="text-xs font-mono text-[var(--color-text-muted)] truncate">
              {citation.file_path}
            </span>
            <div className="flex items-center gap-3 shrink-0 ml-2">
              <span className="text-xs text-[var(--color-text-muted)]">
                L{citation.start_line}–{citation.end_line}
              </span>
              <button
                onClick={() => setExpanded(false)}
                className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
              >
                ✕ Collapse
              </button>
            </div>
          </div>

          {/* Syntax-highlighted code with line numbers starting from actual line */}
          <SyntaxHighlighter
            language={citation.language || "text"}
            style={vscDarkPlus}
            PreTag="div"
            showLineNumbers
            startingLineNumber={citation.start_line || 1}
            customStyle={{
              margin: 0,
              borderRadius: 0,
              maxHeight: "420px",
              fontSize: "12px",
              lineHeight: "1.6",
            }}
          >
            {cleanCode}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  );
}

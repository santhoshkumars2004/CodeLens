"use client";

import React, { use } from "react";
import { useRouter } from "next/navigation";
import ChatWindow from "@/components/ChatWindow";

interface ChatPageProps {
  params: Promise<{ repoId: string }>;
}

export default function ChatPage({ params }: ChatPageProps) {
  const router = useRouter();
  const { repoId: encodedRepoId } = use(params);
  const repoId = decodeURIComponent(encodedRepoId);
  const repoUrl = `https://github.com/${repoId}`;

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <header className="border-b border-[var(--color-border)] px-4 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button
            id="back-btn"
            onClick={() => router.push("/")}
            className="glass rounded-lg p-2 hover:border-[var(--color-border-active)] transition-all"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>

          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center text-xs font-bold">
              S
            </div>
            <div>
              <h1 className="text-sm font-semibold">{repoId}</h1>
              <a
                href={repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
              >
                View on GitHub ↗
              </a>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="glass rounded-full px-3 py-1 text-[10px] text-[var(--color-success)] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-[var(--color-success)] rounded-full animate-pulse" />
            Indexed
          </div>
        </div>
      </header>

      {/* Chat area */}
      <div className="flex-1 overflow-hidden">
        <ChatWindow repoId={repoId} repoUrl={repoUrl} />
      </div>
    </div>
  );
}

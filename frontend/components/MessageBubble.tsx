"use client";

import React from "react";
import CitationCard from "./CitationCard";
import type { Message } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
  repoUrl?: string;
}

export default function MessageBubble({
  message,
  repoUrl,
}: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in-up`}
    >
      <div className={`max-w-[85%] ${isUser ? "order-2" : "order-1"}`}>
        {/* Avatar + Name */}
        <div
          className={`flex items-center gap-2 mb-1.5 ${
            isUser ? "justify-end" : "justify-start"
          }`}
        >
          {!isUser && (
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center text-[10px] font-bold">
              S
            </div>
          )}
          <span className="text-xs text-[var(--color-text-muted)]">
            {isUser ? "You" : "StackSense"}
          </span>
          {message.latency_ms && !isUser && (
            <span className="text-xs text-[var(--color-text-muted)] opacity-60">
              · {(message.latency_ms / 1000).toFixed(1)}s
            </span>
          )}
        </div>

        {/* Message body */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser ? "message-user" : "message-ai"
          }`}
        >
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </div>

          {/* Confidence badge for AI */}
          {!isUser && message.confidence_score !== undefined && (
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1 flex-1 bg-[var(--color-bg-primary)] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[#6366f1] to-[#a855f7] rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.round(message.confidence_score * 100)}%`,
                  }}
                />
              </div>
              <span className="text-xs text-[var(--color-text-muted)]">
                {Math.round(message.confidence_score * 100)}% confidence
              </span>
            </div>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs text-[var(--color-text-muted)] font-medium px-1">
              📚 Sources ({message.citations.length})
            </p>
            {message.citations.map((citation, i) => (
              <CitationCard
                key={i}
                citation={citation}
                index={i}
                repoUrl={repoUrl}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

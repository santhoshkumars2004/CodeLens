"use client";

import React, { useState, useRef, useEffect } from "react";
import MessageBubble from "./MessageBubble";
import type { Message } from "@/lib/types";
import { queryRepo } from "@/lib/api";

interface ChatWindowProps {
  repoId: string;
  repoUrl: string;
}

export default function ChatWindow({ repoId, repoUrl }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await queryRepo(repoId, question);

      const aiMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        citations: response.citations,
        confidence_score: response.confidence_score,
        latency_ms: response.latency_ms,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Sorry, I encountered an error: ${
          error instanceof Error ? error.message : "Unknown error"
        }. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center text-2xl mb-4 animate-pulse-glow">
              🧠
            </div>
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
              Ask anything about the codebase
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] max-w-md">
              I can explain how features work, find specific implementations,
              trace data flows, and more — all with exact file:line citations.
            </p>
            <div className="flex flex-wrap gap-2 mt-6 max-w-lg justify-center">
              {[
                "How does authentication work?",
                "Where is the main entry point?",
                "Explain the database schema",
                "Find error handling patterns",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => { setInput(q); inputRef.current?.focus(); }}
                  className="glass glass-hover rounded-lg px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} repoUrl={repoUrl} />
        ))}

        {isLoading && (
          <div className="flex items-start gap-3 animate-fade-in-up">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#6366f1] to-[#a855f7] flex items-center justify-center text-[10px] font-bold shrink-0 mt-1">
              S
            </div>
            <div className="message-ai rounded-2xl px-4 py-3">
              <div className="dot-pulse">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-[var(--color-border)] p-4">
        <div className="max-w-4xl mx-auto relative">
          <div className="glass rounded-xl p-1.5 flex items-end gap-2">
            <textarea
              ref={inputRef}
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about the codebase..."
              rows={1}
              className="flex-1 bg-transparent text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] outline-none py-2.5 px-3 text-sm resize-none max-h-32"
              disabled={isLoading}
            />
            <button
              id="send-btn"
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="btn-glow text-white p-2.5 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
          <p className="text-[10px] text-[var(--color-text-muted)] mt-1.5 text-center">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}

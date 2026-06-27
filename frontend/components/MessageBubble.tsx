"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import CitationCard from "./CitationCard";
import type { Message } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
  repoUrl?: string;
}

// Parse the raw LLM text into structured sections
function parseResponse(content: string) {
  // Match any combination of old format (EXPLANATION/CODE/SOURCE) or new (## headings)
  const sections: { explanation?: string; code?: string; source?: string; raw?: string } = {};

  // Try to detect section-based format
  const explanationMatch = content.match(
    /(?:##\s*)?(?:📝\s*)?(?:EXPLANATION|Explanation)[:\s]*([\s\S]*?)(?=(?:##\s*)?(?:💻|📄|CODE|Code|SOURCE|Source)|$)/i
  );
  const codeMatch = content.match(
    /(?:##\s*)?(?:💻\s*)?(?:CODE|Code)[:\s]*([\s\S]*?)(?=(?:##\s*)?(?:📄|SOURCE|Source)|$)/i
  );
  const sourceMatch = content.match(
    /(?:##\s*)?(?:📄\s*)?(?:SOURCE|Source)[:\s]*([\s\S]*?)$/i
  );

  if (explanationMatch) sections.explanation = explanationMatch[1].trim();
  if (codeMatch) sections.code = codeMatch[1].trim();
  if (sourceMatch) sections.source = sourceMatch[1].trim();

  // If nothing parsed, treat as plain markdown
  if (!sections.explanation && !sections.code) {
    sections.raw = content;
  }

  return sections;
}

function CodeBlock({ children, language }: { children: string; language?: string }) {
  return (
    <SyntaxHighlighter
      PreTag="div"
      language={language || "text"}
      style={vscDarkPlus}
      className="rounded-xl !my-0 text-xs"
      customStyle={{ margin: 0, borderRadius: "12px" }}
    >
      {children.replace(/\n$/, "")}
    </SyntaxHighlighter>
  );
}

function StructuredAnswer({
  explanation,
  code,
  source,
}: {
  explanation?: string;
  code?: string;
  source?: string;
}) {
  // Extract language and code from a code block if present in the code string
  let codeContent = code || "";
  let codeLang = "text";
  const fencedMatch = codeContent.match(/^```(\w*)\n?([\s\S]*?)```$/m);
  if (fencedMatch) {
    codeLang = fencedMatch[1] || "text";
    codeContent = fencedMatch[2];
  }

  return (
    <div className="space-y-3">
      {explanation && (
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-base">📝</span>
            <span className="text-xs font-semibold uppercase tracking-widest text-[var(--color-accent)] opacity-80">
              Explanation
            </span>
          </div>
          <p className="text-sm leading-relaxed text-[var(--color-text-primary)]">
            {explanation}
          </p>
        </div>
      )}

      {code && (
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-base">💻</span>
            <span className="text-xs font-semibold uppercase tracking-widest text-[var(--color-accent)] opacity-80">
              Code
            </span>
          </div>
          <div className="rounded-xl overflow-hidden border border-[var(--color-border)] bg-[#1e1e1e]">
            <CodeBlock language={codeLang}>{codeContent}</CodeBlock>
          </div>
        </div>
      )}

      {source && (
        <div className="flex items-start gap-2 mt-1">
          <span className="text-sm">📄</span>
          <span className="text-xs text-[var(--color-text-muted)] font-mono">
            {source}
          </span>
        </div>
      )}
    </div>
  );
}

export default function MessageBubble({
  message,
  repoUrl,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const parsed = !isUser ? parseResponse(message.content) : null;

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
            {isUser ? "You" : "CodeLens"}
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
          <div className="text-sm leading-relaxed">
            {isUser || !parsed ? (
              /* Plain markdown for user messages or unstructured AI responses */
              <ReactMarkdown
                components={{
                  code(props) {
                    const { children, className, node, ref, ...rest } = props;
                    const match = /language-(\w+)/.exec(className || "");
                    return match ? (
                      <SyntaxHighlighter
                        {...rest}
                        PreTag="div"
                        language={match[1]}
                        style={vscDarkPlus}
                        className="rounded-lg !my-2 text-xs"
                      >
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    ) : (
                      <code
                        {...rest}
                        className="bg-[var(--color-bg-primary)] px-1.5 py-0.5 rounded text-[var(--color-accent)] font-mono text-xs"
                      >
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            ) : parsed.raw ? (
              /* Unstructured AI response — render as markdown */
              <ReactMarkdown
                components={{
                  code(props) {
                    const { children, className, node, ref, ...rest } = props;
                    const match = /language-(\w+)/.exec(className || "");
                    return match ? (
                      <SyntaxHighlighter
                        {...rest}
                        PreTag="div"
                        language={match[1]}
                        style={vscDarkPlus}
                        className="rounded-lg !my-2 text-xs"
                      >
                        {String(children).replace(/\n$/, "")}
                      </SyntaxHighlighter>
                    ) : (
                      <code
                        {...rest}
                        className="bg-[var(--color-bg-primary)] px-1.5 py-0.5 rounded text-[var(--color-accent)] font-mono text-xs"
                      >
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {parsed.raw}
              </ReactMarkdown>
            ) : (
              /* Structured AI response — render as beautiful sections */
              <StructuredAnswer
                explanation={parsed.explanation}
                code={parsed.code}
                source={parsed.source}
              />
            )}
          </div>

          {/* Confidence badge for AI */}
          {!isUser && message.confidence_score !== undefined && (
            <div className="mt-3 flex items-center gap-2">
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

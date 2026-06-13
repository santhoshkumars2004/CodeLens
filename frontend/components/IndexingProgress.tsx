"use client";

import React from "react";

interface IndexingProgressProps {
  progress: number;
  status: string;
  message: string;
}

export default function IndexingProgress({
  progress,
  status,
  message,
}: IndexingProgressProps) {
  const steps = [
    { label: "Cloning", threshold: 20 },
    { label: "Discovering", threshold: 40 },
    { label: "Chunking", threshold: 60 },
    { label: "Embedding", threshold: 80 },
    { label: "Storing", threshold: 100 },
  ];

  return (
    <div className="w-full max-w-xl mx-auto mt-8 animate-fade-in-up">
      <div className="glass rounded-xl p-6">
        {/* Progress bar */}
        <div className="relative h-2 bg-[var(--color-bg-primary)] rounded-full overflow-hidden mb-4">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-[#6366f1] to-[#a855f7] rounded-full transition-all duration-700 ease-out"
            style={{ width: `${progress}%` }}
          />
          <div className="absolute inset-0 animate-shimmer rounded-full" />
        </div>

        {/* Steps */}
        <div className="flex justify-between mb-4">
          {steps.map((step, i) => (
            <div key={step.label} className="flex flex-col items-center gap-1.5">
              <div
                className={`w-3 h-3 rounded-full transition-all duration-300 ${
                  progress >= step.threshold
                    ? "bg-[var(--color-accent)] shadow-[0_0_8px_var(--color-accent-glow)]"
                    : progress >= step.threshold - 20
                    ? "bg-[var(--color-accent)] animate-pulse"
                    : "bg-[var(--color-border)]"
                }`}
              />
              <span
                className={`text-xs ${
                  progress >= step.threshold - 20
                    ? "text-[var(--color-text-primary)]"
                    : "text-[var(--color-text-muted)]"
                }`}
              >
                {step.label}
              </span>
            </div>
          ))}
        </div>

        {/* Status message */}
        <p className="text-center text-sm text-[var(--color-text-secondary)]">
          {message}
        </p>

        {/* Percentage */}
        <p className="text-center text-2xl font-bold gradient-text mt-2">
          {progress}%
        </p>
      </div>
    </div>
  );
}

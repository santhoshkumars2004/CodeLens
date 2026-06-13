import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "StackSense — AI Codebase Q&A",
  description:
    "Ask questions about any GitHub repository and get precise, cited answers with exact file and line references.",
  keywords: ["AI", "codebase", "Q&A", "RAG", "GitHub", "code analysis"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased min-h-screen">{children}</body>
    </html>
  );
}

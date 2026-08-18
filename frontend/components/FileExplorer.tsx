"use client";

import React, { useState, useEffect, useCallback } from "react";
import { getRepoFiles, type RepoFile } from "@/lib/api";

const LANG_COLORS: Record<string, string> = {
  python:     "#3572A5",
  typescript: "#2b7489",
  javascript: "#f1e05a",
  css:        "#563d7c",
  markdown:   "#083fa1",
  json:       "#292929",
  yaml:       "#cb171e",
  shell:      "#89e051",
  dockerfile: "#384d54",
  sql:        "#e38c00",
  unknown:    "#6e7681",
};

const LANG_ICONS: Record<string, string> = {
  python:     "??",
  typescript: "??",
  javascript: "??",
  css:        "??",
  markdown:   "??",
  json:       "??",
  yaml:       "??",
  shell:      "??",
  dockerfile: "??",
  sql:        "???",
  unknown:    "??",
};

interface TreeNode {
  name: string;
  path: string;
  type: "file" | "dir";
  language?: string;
  chunk_count?: number;
  children?: TreeNode[];
}

function buildTree(files: RepoFile[]): TreeNode[] {
  const root: Record<string, any> = {};
  for (const file of files) {
    const parts = file.file_path.replace(/\\/g, "/").split("/");
    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1;
      const fullPath = parts.slice(0, i + 1).join("/");
      if (!current[part]) {
        current[part] = { name: part, path: fullPath, type: isFile ? "file" : "dir",
          language: isFile ? file.language : undefined,
          chunk_count: isFile ? file.chunk_count : undefined,
          children: isFile ? undefined : {} };
      }
      if (!isFile) current = current[part].children;
    }
  }
  function toArray(nodeMap: Record<string, any>): TreeNode[] {
    return Object.values(nodeMap).map((n: any) => ({
      ...n, children: n.children ? toArray(n.children) : undefined,
    })).sort((a, b) => a.type !== b.type ? (a.type === "dir" ? -1 : 1) : a.name.localeCompare(b.name));
  }
  return toArray(root);
}

function TreeItem({ node, depth, selectedPath, onSelect }: {
  node: TreeNode; depth: number; selectedPath: string | null; onSelect: (p: string | null) => void;
}) {
  const [open, setOpen] = useState(depth < 2);
  const isSelected = selectedPath === node.path;
  const langColor = LANG_COLORS[node.language ?? "unknown"] ?? LANG_COLORS.unknown;
  const langIcon  = LANG_ICONS[node.language  ?? "unknown"] ?? LANG_ICONS.unknown;

  if (node.type === "dir") {
    return (
      <div>
        <button onClick={() => setOpen(!open)}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          className="w-full flex items-center gap-1.5 py-[3px] pr-2 text-left hover:bg-white/5 rounded transition-colors">
          <span className="text-[10px] text-[var(--color-text-muted)] w-3 shrink-0 transition-transform duration-150"
                style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>?</span>
          <span className="text-xs">??</span>
          <span className="text-xs text-[var(--color-text)] font-medium truncate flex-1">{node.name}</span>
        </button>
        {open && node.children && (
          <div>{node.children.map(c => <TreeItem key={c.path} node={c} depth={depth+1} selectedPath={selectedPath} onSelect={onSelect}/>)}</div>
        )}
      </div>
    );
  }

  return (
    <button onClick={() => onSelect(isSelected ? null : node.path)}
      style={{ paddingLeft: `${depth * 12 + 8}px` }}
      title={`${node.path} - ${node.chunk_count} chunks`}
      className={`w-full flex items-center gap-1.5 py-[3px] pr-2 text-left rounded transition-all group ${
        isSelected ? "bg-[var(--color-accent)]/15 border-l-2 border-[var(--color-accent)]" : "hover:bg-white/5"}`}>
      <span className="text-[10px] shrink-0">{langIcon}</span>
      <span className="text-xs text-[var(--color-text-muted)] truncate flex-1 group-hover:text-[var(--color-text)] transition-colors">{node.name}</span>
      {node.chunk_count !== undefined && (
        <span className="text-[8px] px-1 py-0.5 rounded shrink-0 opacity-60"
              style={{ backgroundColor: langColor + "33", color: langColor }}>{node.chunk_count}</span>
      )}
    </button>
  );
}

interface FileExplorerProps {
  repoId: string;
  onFileSelect: (filePath: string | null) => void;
  selectedFile: string | null;
}

export default function FileExplorer({ repoId, onFileSelect, selectedFile }: FileExplorerProps) {
  const [tree, setTree]       = useState<TreeNode[]>([]);
  const [stats, setStats]     = useState<{ files: number; chunks: number; langs: string[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [search, setSearch]   = useState("");
  const [collapsed, setCollapsed] = useState(false);

  const flatFiles: RepoFile[] = [];
  const collectFiles = useCallback((nodes: TreeNode[]) => {
    for (const n of nodes) {
      if (n.type === "file") flatFiles.push({ file_path: n.path, language: n.language ?? "unknown", chunk_count: n.chunk_count ?? 0 });
      if (n.children) collectFiles(n.children);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree]);

  useEffect(() => {
    setLoading(true); setError(null);
    getRepoFiles(repoId)
      .then(d => { setTree(buildTree(d.files)); setStats({ files: d.total_files, chunks: d.total_chunks, langs: d.languages }); })
      .catch(e => setError(e.message || "Failed to load files"))
      .finally(() => setLoading(false));
  }, [repoId]);

  collectFiles(tree);
  const filteredFiles = search.trim()
    ? flatFiles.filter(f => f.file_path.toLowerCase().includes(search.toLowerCase()))
    : null;

  if (collapsed) {
    return (
      <button onClick={() => setCollapsed(false)} title="Show file explorer"
        className="flex flex-col items-center justify-center w-8 h-full border-r border-[var(--color-border)] hover:bg-white/5 transition-colors gap-2 shrink-0">
        <span className="text-sm rotate-90">??</span>
        <span className="text-[8px] text-[var(--color-text-muted)] [writing-mode:vertical-rl]">Files</span>
      </button>
    );
  }

  return (
    <aside className="w-56 shrink-0 border-r border-[var(--color-border)] flex flex-col h-full overflow-hidden" style={{ background: "rgba(0,0,0,0.3)" }}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] shrink-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs">??</span>
          <span className="text-xs font-semibold text-[var(--color-text)]">Files</span>
          {stats && <span className="text-[9px] text-[var(--color-text-muted)] bg-white/5 px-1 rounded">{stats.files}</span>}
        </div>
        <button onClick={() => setCollapsed(true)} title="Collapse"
          className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors p-0.5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
      </div>

      {stats && (
        <div className="px-3 py-1.5 border-b border-[var(--color-border)] flex items-center gap-2 flex-wrap shrink-0">
          <span className="text-[9px] text-[var(--color-text-muted)]">{stats.chunks} chunks</span>
          <span className="text-[9px] text-[var(--color-border)]">·</span>
          <div className="flex gap-1 flex-wrap">
            {stats.langs.slice(0, 4).map(lang => (
              <span key={lang} className="text-[8px] px-1 rounded"
                style={{ backgroundColor: (LANG_COLORS[lang] ?? "#6e7681") + "25", color: LANG_COLORS[lang] ?? "#6e7681" }}>
                {lang}
              </span>
            ))}
            {stats.langs.length > 4 && <span className="text-[8px] text-[var(--color-text-muted)]">+{stats.langs.length - 4}</span>}
          </div>
        </div>
      )}

      <div className="px-2 py-1.5 border-b border-[var(--color-border)] shrink-0">
        <div className="relative">
          <svg className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter files..."
            className="w-full bg-white/5 border border-[var(--color-border)] rounded text-[10px] text-[var(--color-text)] placeholder-[var(--color-text-muted)] pl-6 pr-2 py-1 outline-none focus:border-[var(--color-accent)]/50 transition-colors"/>
        </div>
      </div>

      {selectedFile && (
        <div className="px-2 py-1.5 border-b border-[var(--color-accent)]/30 bg-[var(--color-accent)]/10 flex items-center justify-between shrink-0">
          <span className="text-[9px] text-[var(--color-accent)] truncate flex-1">?? {selectedFile.split("/").pop()}</span>
          <button onClick={() => onFileSelect(null)} className="text-[var(--color-accent)] hover:text-[var(--color-text)] transition-colors ml-1 shrink-0">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto py-1">
        {loading && (
          <div className="flex items-center justify-center h-20 gap-2">
            <div className="w-3 h-3 border border-[var(--color-accent)] border-t-transparent rounded-full animate-spin"/>
            <span className="text-[10px] text-[var(--color-text-muted)]">Loading...</span>
          </div>
        )}
        {error && <div className="px-3 py-2 text-[10px] text-red-400">{error}</div>}
        {!loading && !error && filteredFiles && (
          <div>
            {filteredFiles.length === 0 && <div className="px-3 py-2 text-[10px] text-[var(--color-text-muted)]">No files match</div>}
            {filteredFiles.map(f => {
              const name = f.file_path.split("/").pop() ?? f.file_path;
              const lc = LANG_COLORS[f.language] ?? LANG_COLORS.unknown;
              const li = LANG_ICONS[f.language]  ?? LANG_ICONS.unknown;
              const isSel = selectedFile === f.file_path;
              return (
                <button key={f.file_path} onClick={() => onFileSelect(isSel ? null : f.file_path)}
                  className={`w-full flex items-center gap-1.5 py-[3px] px-2 text-left rounded transition-all ${isSel ? "bg-[var(--color-accent)]/15" : "hover:bg-white/5"}`}
                  title={f.file_path}>
                  <span className="text-[10px]">{li}</span>
                  <span className="text-xs text-[var(--color-text-muted)] truncate flex-1">{name}</span>
                  <span className="text-[8px] px-1 py-0.5 rounded shrink-0" style={{ backgroundColor: lc+"33", color: lc }}>{f.chunk_count}</span>
                </button>
              );
            })}
          </div>
        )}
        {!loading && !error && !filteredFiles && (
          <div>{tree.map(n => <TreeItem key={n.path} node={n} depth={0} selectedPath={selectedFile} onSelect={onFileSelect}/>)}</div>
        )}
      </div>

      <div className="px-3 py-1.5 border-t border-[var(--color-border)] shrink-0">
        <p className="text-[8px] text-[var(--color-text-muted)] leading-relaxed">Click a file to filter answers to that file only.</p>
      </div>
    </aside>
  );
}

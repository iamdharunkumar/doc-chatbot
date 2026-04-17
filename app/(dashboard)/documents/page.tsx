"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { documentsApi, Document } from "@/lib/api";
import {
  FileText, Music, Video, Trash2, RefreshCw,
  MessageSquare, Clock, Upload, AlertCircle, Loader2, Search
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow } from "date-fns";

function StatusBadge({ status }: { status: Document["status"] }) {
  const map = {
    pending:    { label: "Pending",    cls: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400" },
    processing: { label: "Processing", cls: "bg-blue-500/15 text-blue-600 dark:text-blue-400 status-processing" },
    ready:      { label: "Ready",      cls: "bg-green-500/15 text-green-600 dark:text-green-400" },
    error:      { label: "Error",      cls: "bg-destructive/15 text-destructive" },
  };
  const { label, cls } = map[status] ?? map.pending;
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium", cls)}>
      {status === "processing" && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
      {label}
    </span>
  );
}

function FileTypeIcon({ type }: { type: Document["file_type"] }) {
  if (type === "audio") return <Music className="w-5 h-5 text-green-500" />;
  if (type === "video") return <Video className="w-5 h-5 text-blue-500" />;
  return <FileText className="w-5 h-5 text-primary" />;
}

function formatSize(bytes: number) {
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function formatDuration(secs?: number) {
  if (!secs) return null;
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await documentsApi.list(0, 50);
      setDocs(res.data.items);
      setTotal(res.data.total);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh if any doc is processing
  useEffect(() => {
    const hasProcessing = docs.some((d) => d.status === "processing" || d.status === "pending");
    if (!hasProcessing) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [docs, load]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this document? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await documentsApi.delete(id);
      setDocs((d) => d.filter((doc) => doc.id !== id));
    } finally {
      setDeleting(null);
    }
  }

  const filtered = docs.filter((d) =>
    d.original_filename.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">My Documents</h1>
          <p className="text-muted-foreground text-sm mt-0.5">{total} document{total !== 1 ? "s" : ""} total</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            id="refresh-docs"
            onClick={load}
            className="p-2 rounded-xl border border-border hover:bg-muted transition"
            title="Refresh"
          >
            <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
          </button>
          <Link
            href="/upload"
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground
                       text-sm font-semibold hover:opacity-90 transition glow"
          >
            <Upload className="w-4 h-4" /> Upload
          </Link>
        </div>
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          id="doc-search"
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search documents…"
          className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-border bg-background
                     text-sm outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition"
        />
      </div>

      {/* List */}
      {loading && docs.length === 0 ? (
        <div className="flex items-center justify-center py-24 text-muted-foreground">
          <Loader2 className="w-6 h-6 animate-spin mr-2" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
          <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center">
            <FileText className="w-8 h-8 text-muted-foreground" />
          </div>
          <div>
            <p className="font-semibold">No documents yet</p>
            <p className="text-sm text-muted-foreground">Upload a PDF, audio, or video to get started</p>
          </div>
          <Link
            href="/upload"
            className="px-5 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:opacity-90 transition"
          >
            Upload your first file
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((doc) => (
            <div
              key={doc.id}
              className="group flex items-center gap-4 p-4 rounded-2xl border border-border
                         bg-card hover:border-primary/30 hover:shadow-md transition-all duration-200"
            >
              {/* Icon */}
              <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center shrink-0">
                <FileTypeIcon type={doc.file_type} />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-medium text-sm truncate max-w-xs">{doc.original_filename}</p>
                  <StatusBadge status={doc.status} />
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                  <span>{formatSize(doc.file_size)}</span>
                  {doc.duration_seconds && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />{formatDuration(doc.duration_seconds)}
                    </span>
                  )}
                  <span>{formatDistanceToNow(new Date(doc.created_at), { addSuffix: true })}</span>
                </div>
                {doc.status === "error" && doc.error_message && (
                  <p className="flex items-center gap-1 mt-1 text-xs text-destructive">
                    <AlertCircle className="w-3 h-3" />{doc.error_message}
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                {doc.status === "ready" && (
                  <Link
                    href={`/documents/${doc.id}`}
                    id={`chat-doc-${doc.id}`}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground
                               text-xs font-semibold hover:opacity-90 transition"
                  >
                    <MessageSquare className="w-3.5 h-3.5" /> Chat
                  </Link>
                )}
                <button
                  id={`delete-doc-${doc.id}`}
                  onClick={() => handleDelete(doc.id)}
                  disabled={deleting === doc.id}
                  className="p-1.5 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10
                             transition disabled:opacity-50"
                >
                  {deleting === doc.id
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <Trash2 className="w-4 h-4" />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

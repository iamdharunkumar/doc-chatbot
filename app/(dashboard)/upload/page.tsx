"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { documentsApi } from "@/lib/api";
import {
  Upload, FileText, Music, Video, CheckCircle2,
  XCircle, Loader2, ArrowRight, AlertCircle
} from "lucide-react";
import { cn } from "@/lib/utils";

type UploadState = "idle" | "uploading" | "success" | "error";

const ACCEPT = {
  "application/pdf": [".pdf"],
  "audio/mpeg": [".mp3"],
  "audio/wav": [".wav"],
  "audio/mp4": [".m4a"],
  "audio/ogg": [".ogg"],
  "audio/flac": [".flac"],
  "video/mp4": [".mp4"],
  "video/x-matroska": [".mkv"],
  "video/quicktime": [".mov"],
  "video/webm": [".webm"],
};

function FileIcon({ type }: { type: string }) {
  if (type.startsWith("audio")) return <Music className="w-6 h-6 text-green-500" />;
  if (type.startsWith("video")) return <Video className="w-6 h-6 text-blue-500" />;
  return <FileText className="w-6 h-6 text-primary" />;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [state, setState] = useState<UploadState>("idle");
  const [error, setError] = useState("");
  const [docId, setDocId] = useState<string | null>(null);

  const handleFile = (f: File) => {
    setFile(f);
    setState("idle");
    setError("");
    setProgress(0);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  }, []);

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  async function handleUpload() {
    if (!file) return;
    setState("uploading");
    setProgress(0);
    try {
      const res = await documentsApi.upload(file, setProgress);
      setDocId(res.data.id);
      setState("success");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed. Please try again.");
      setState("error");
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Upload a Document</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Supports PDF, audio (MP3, WAV, M4A, OGG, FLAC) and video (MP4, MKV, MOV, WebM) files up to 500 MB.
        </p>
      </div>

      {/* Drop zone */}
      <div
        id="drop-zone"
        className={cn(
          "drop-zone p-10 min-h-[240px]",
          isDragging && "active",
          state === "success" && "border-green-500/60 bg-green-500/5",
          state === "error" && "border-destructive/50 bg-destructive/5"
        )}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        <input
          id="file-input"
          type="file"
          className="hidden"
          accept=".pdf,.mp3,.wav,.m4a,.ogg,.flac,.mp4,.mkv,.mov,.webm"
          onChange={handleInput}
        />

        {state === "success" ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <CheckCircle2 className="w-14 h-14 text-green-500" />
            <p className="font-semibold text-green-600 dark:text-green-400">Upload successful!</p>
            <p className="text-sm text-muted-foreground">Your document is being processed in the background.</p>
          </div>
        ) : state === "error" ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <XCircle className="w-12 h-12 text-destructive" />
            <p className="font-semibold text-destructive">{error}</p>
            <p className="text-sm text-muted-foreground">Click to try again</p>
          </div>
        ) : file ? (
          <div className="flex flex-col items-center gap-4 text-center pointer-events-none">
            <FileIcon type={file.type} />
            <div>
              <p className="font-semibold truncate max-w-xs">{file.name}</p>
              <p className="text-sm text-muted-foreground">{formatSize(file.size)}</p>
            </div>
            {state === "uploading" && (
              <div className="w-full max-w-xs space-y-2">
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{progress}%</p>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
              <Upload className="w-8 h-8 text-primary" />
            </div>
            <div>
              <p className="font-semibold">Drop your file here</p>
              <p className="text-sm text-muted-foreground">or click to browse</p>
            </div>
            <div className="flex gap-3 text-xs text-muted-foreground">
              {[["PDF", "text-primary", FileText], ["Audio", "text-green-500", Music], ["Video", "text-blue-500", Video]].map(
                ([label, cls, Icon]: any) => (
                  <span key={label} className={cn("flex items-center gap-1", cls)}>
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                  </span>
                )
              )}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="mt-6 flex items-center justify-between gap-4">
        {file && state !== "success" && (
          <button
            onClick={() => { setFile(null); setState("idle"); }}
            className="text-sm text-muted-foreground hover:text-foreground transition"
          >
            Clear
          </button>
        )}
        <div className="ml-auto flex gap-3">
          {state === "success" && docId && (
            <button
              id="go-to-doc"
              onClick={() => router.push(`/documents/${docId}`)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-primary-foreground
                         text-sm font-semibold hover:opacity-90 transition glow"
            >
              Open Document <ArrowRight className="w-4 h-4" />
            </button>
          )}
          {file && state !== "success" && (
            <button
              id="upload-btn"
              onClick={handleUpload}
              disabled={state === "uploading"}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-primary text-primary-foreground
                         text-sm font-semibold hover:opacity-90 disabled:opacity-60 transition glow"
            >
              {state === "uploading" ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Uploading…</>
              ) : (
                <><Upload className="w-4 h-4" /> Upload</>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Tips */}
      <div className="mt-10 rounded-2xl border border-border bg-muted/40 p-5">
        <div className="flex gap-3">
          <AlertCircle className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div className="space-y-1.5 text-sm">
            <p className="font-medium">What happens after upload?</p>
            <ul className="space-y-1 text-muted-foreground list-disc pl-4">
              <li>PDFs are parsed and split into searchable chunks</li>
              <li>Audio/video files are transcribed with timestamps using Whisper</li>
              <li>All content is embedded using AI for semantic search</li>
              <li>You can start chatting once status shows "Ready"</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

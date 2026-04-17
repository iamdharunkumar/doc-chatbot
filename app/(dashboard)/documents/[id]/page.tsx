"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { documentsApi, chatApi, Document, ChatMessage, ChatSession, TimestampEntry } from "@/lib/api";
import { getToken } from "@/lib/auth";
import {
  Send, Loader2, FileText, Music, Video, Play, ChevronDown,
  ChevronUp, BookOpen, Clock, ArrowLeft, RefreshCw, Sparkles
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatDistanceToNow, format } from "date-fns";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Timestamp Player ─────────────────────────────────────────────────────────
function TimestampPlayer({
  timestamps,
  mediaUrl,
  fileType,
}: {
  timestamps: TimestampEntry[];
  mediaUrl: string;
  fileType: string;
}) {
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);

  function jumpTo(start: number) {
    const el = mediaRef.current;
    if (el) { el.currentTime = start; el.play(); }
  }

  function formatTime(s: number) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  }

  return (
    <div className="space-y-3">
      {fileType === "video" ? (
        <video
          ref={mediaRef as React.RefObject<HTMLVideoElement>}
          src={mediaUrl}
          controls
          className="w-full rounded-xl aspect-video bg-black"
        />
      ) : (
        <audio
          ref={mediaRef as React.RefObject<HTMLAudioElement>}
          src={mediaUrl}
          controls
          className="w-full"
        />
      )}

      {timestamps.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Relevant segments</p>
          {timestamps.map((ts, i) => (
            <button
              key={i}
              id={`timestamp-${i}`}
              onClick={() => jumpTo(ts.start)}
              className="w-full text-left flex items-start gap-3 p-3 rounded-xl border border-border
                         hover:border-primary/40 hover:bg-primary/5 transition group"
            >
              <div className="shrink-0 flex flex-col items-center gap-0.5 mt-0.5">
                <span className="text-xs font-mono text-primary">{formatTime(ts.start)}</span>
                <span className="text-xs text-muted-foreground">→ {formatTime(ts.end)}</span>
              </div>
              <p className="flex-1 text-xs text-muted-foreground line-clamp-2 group-hover:text-foreground transition">
                {ts.text}
              </p>
              <Play className="w-4 h-4 text-primary shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Chat Message ─────────────────────────────────────────────────────────────
function ChatBubble({
  message,
  isStreaming = false,
}: {
  message: ChatMessage | { role: string; content: string; id: string; created_at: string };
  isStreaming?: boolean;
}) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
        )}
      >
        {isUser ? "U" : <Sparkles className="w-4 h-4 text-primary" />}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-3",
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-sm"
            : "bg-card border border-border rounded-tl-sm"
        )}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className={cn("prose-chat", isUser && "text-primary-foreground")}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-flex gap-1 ml-1">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export default function DocumentChatPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [doc, setDoc] = useState<Document | null>(null);
  const [messages, setMessages] = useState<
    (ChatMessage | { role: string; content: string; id: string; created_at: string })[]
  >([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamContent, setStreamContent] = useState("");
  const [loading, setLoading] = useState(true);

  // Panels
  const [showSummary, setShowSummary] = useState(false);
  const [summaryText, setSummaryText] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [showTimestamps, setShowTimestamps] = useState(false);
  const [timestamps, setTimestamps] = useState<TimestampEntry[]>([]);
  const [mediaUrl, setMediaUrl] = useState<string | null>(null);
  const [timestampQuery, setTimestampQuery] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, streamContent]);

  // Load document
  useEffect(() => {
    (async () => {
      try {
        const res = await documentsApi.get(docId);
        setDoc(res.data);
        if (res.data.status !== "ready") {
          router.replace("/documents");
          return;
        }
        // Load sessions
        const sessRes = await chatApi.sessions(docId);
        setSessions(sessRes.data);
        if (sessRes.data.length > 0) {
          const latest = sessRes.data[0];
          setCurrentSessionId(latest.id);
          const histRes = await chatApi.history(latest.id);
          setMessages(histRes.data.messages);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [docId, router]);

  async function sendMessage() {
    if (!input.trim() || streaming) return;
    const question = input.trim();
    setInput("");

    const userMsg = { id: crypto.randomUUID(), role: "user", content: question, created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);
    setStreamContent("");

    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/chat/${docId}/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({ question, session_id: currentSessionId }),
      });

      if (!res.ok || !res.body) throw new Error("Stream failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let full = "";
      let resolvedSessionId: string | null = currentSessionId;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") break;
          // First message carries session id
          if (payload.startsWith("{") && payload.includes("session_id")) {
            try {
              const parsed = JSON.parse(payload);
              if (parsed.session_id) {
                resolvedSessionId = parsed.session_id;
                setCurrentSessionId(parsed.session_id);
              }
            } catch {}
            continue;
          }
          const token = payload.replace(/\\n/g, "\n");
          full += token;
          setStreamContent(full);
        }
      }

      const assistantMsg = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: full,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Auto-fetch timestamps if audio/video
      if (doc?.file_type !== "pdf" && full) {
        fetchTimestamps(question);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: "⚠️ Something went wrong. Please try again.", created_at: new Date().toISOString() },
      ]);
    } finally {
      setStreaming(false);
      setStreamContent("");
    }
  }

  async function loadSummary() {
    if (summaryText) { setShowSummary(true); return; }
    setSummaryLoading(true);
    setShowSummary(true);
    try {
      const res = await documentsApi.summarize(docId);
      setSummaryText(res.data.summary);
    } finally {
      setSummaryLoading(false);
    }
  }

  async function fetchTimestamps(query: string) {
    try {
      const [tsRes, urlRes] = await Promise.all([
        documentsApi.timestamps(docId, query),
        documentsApi.presignedUrl(docId),
      ]);
      setTimestamps(tsRes.data.timestamps);
      setMediaUrl(urlRes.data.url);
      setShowTimestamps(true);
    } catch {}
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!doc) return null;

  const isMediaDoc = doc.file_type !== "pdf";

  return (
    <div className="flex h-full">
      {/* ── Main chat area ── */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-10">
          <button
            onClick={() => router.push("/documents")}
            className="p-1.5 rounded-lg hover:bg-muted transition text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
            {doc.file_type === "audio" ? <Music className="w-4 h-4 text-green-500" />
              : doc.file_type === "video" ? <Video className="w-4 h-4 text-blue-500" />
              : <FileText className="w-4 h-4 text-primary" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold truncate">{doc.original_filename}</p>
            <p className="text-xs text-muted-foreground">Ready · {messages.length} messages</p>
          </div>

          {/* Summary button */}
          <button
            id="summary-btn"
            onClick={loadSummary}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-medium
                       hover:bg-muted transition"
          >
            <BookOpen className="w-3.5 h-3.5" /> Summary
          </button>

          {/* Timestamps button - only for media */}
          {isMediaDoc && (
            <button
              id="timestamps-btn"
              onClick={() => setShowTimestamps(!showTimestamps)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-medium
                         hover:bg-muted transition"
            >
              <Clock className="w-3.5 h-3.5" /> Timestamps
            </button>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
          {messages.length === 0 && !streaming && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center py-16">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
                <Sparkles className="w-7 h-7 text-primary" />
              </div>
              <div>
                <p className="font-semibold">Ask anything about this document</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {isMediaDoc
                    ? "I'll answer with references to specific timestamps."
                    : "I'll answer using the document content only."}
                </p>
              </div>
              {/* Suggested questions */}
              <div className="flex flex-wrap gap-2 justify-center max-w-sm">
                {["Summarize this document", "What are the key points?", "What topics are covered?"].map((q) => (
                  <button
                    key={q}
                    onClick={() => { setInput(q); inputRef.current?.focus(); }}
                    className="px-3 py-1.5 text-xs rounded-full border border-border hover:border-primary/40
                               hover:bg-primary/5 transition text-muted-foreground hover:text-foreground"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <ChatBubble key={msg.id} message={msg} />
          ))}

          {streaming && streamContent && (
            <ChatBubble
              message={{ id: "streaming", role: "assistant", content: streamContent, created_at: "" }}
              isStreaming
            />
          )}

          {streaming && !streamContent && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-primary" />
              </div>
              <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
                <span className="inline-flex gap-1">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-border bg-card/50 backdrop-blur-sm">
          <div className="flex items-end gap-3 rounded-2xl border border-border bg-background p-2
                          focus-within:ring-2 focus-within:ring-primary/30 focus-within:border-primary transition">
            <textarea
              ref={inputRef}
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
              className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none
                         placeholder:text-muted-foreground/60 max-h-40 overflow-y-auto"
              style={{ minHeight: "36px" }}
              onInput={(e) => {
                const t = e.currentTarget;
                t.style.height = "auto";
                t.style.height = `${Math.min(t.scrollHeight, 160)}px`;
              }}
            />
            <button
              id="send-btn"
              onClick={sendMessage}
              disabled={!input.trim() || streaming}
              className="shrink-0 p-2 rounded-xl bg-primary text-primary-foreground hover:opacity-90
                         disabled:opacity-40 transition active:scale-95"
            >
              {streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-muted-foreground text-center mt-2">
            Powered by Llama 3.1 70B · Answers based on document content only
          </p>
        </div>
      </div>

      {/* ── Right panel: Summary / Timestamps ── */}
      {(showSummary || showTimestamps) && (
        <div className="w-80 shrink-0 border-l border-border flex flex-col overflow-hidden bg-card/30">
          {showSummary && (
            <div className="flex flex-col border-b border-border">
              <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <BookOpen className="w-4 h-4 text-primary" /> Summary
                </div>
                <button onClick={() => setShowSummary(false)} className="text-muted-foreground hover:text-foreground">
                  <ChevronUp className="w-4 h-4" />
                </button>
              </div>
              <div className="px-4 pb-4 text-sm text-muted-foreground overflow-y-auto max-h-72">
                {summaryLoading ? (
                  <div className="flex items-center gap-2 py-4">
                    <Loader2 className="w-4 h-4 animate-spin" /> Generating summary…
                  </div>
                ) : summaryText ? (
                  <div className="prose-chat">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{summaryText}</ReactMarkdown>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          {showTimestamps && isMediaDoc && (
            <div className="flex flex-col flex-1 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Clock className="w-4 h-4 text-primary" /> Timestamps
                </div>
                <button onClick={() => setShowTimestamps(false)} className="text-muted-foreground hover:text-foreground">
                  <ChevronUp className="w-4 h-4" />
                </button>
              </div>
              {/* Query input */}
              <div className="px-4 py-3 border-b border-border">
                <div className="flex gap-2">
                  <input
                    id="timestamp-query"
                    type="text"
                    value={timestampQuery}
                    onChange={(e) => setTimestampQuery(e.target.value)}
                    placeholder="Search timestamps…"
                    className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-border bg-background
                               outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition"
                    onKeyDown={(e) => { if (e.key === "Enter" && timestampQuery) fetchTimestamps(timestampQuery); }}
                  />
                  <button
                    onClick={() => timestampQuery && fetchTimestamps(timestampQuery)}
                    className="px-2 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs hover:opacity-90 transition"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto px-4 py-4">
                {mediaUrl ? (
                  <TimestampPlayer
                    timestamps={timestamps}
                    mediaUrl={mediaUrl}
                    fileType={doc.file_type}
                  />
                ) : (
                  <p className="text-xs text-muted-foreground">Ask a question first to find relevant timestamps.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

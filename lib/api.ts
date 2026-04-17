import axios, { AxiosInstance, InternalAxiosRequestConfig } from "axios";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 
  (typeof window !== "undefined" ? window.location.origin : "http://localhost:3000");

// In production (Vercel), we don't want the /api prefix if calling Render directly,
// OR we keep it if Render handles /api. Let's assume standard behavior:
const api: AxiosInstance = axios.create({
  baseURL: API_URL.includes("localhost") ? `${API_URL}/api` : API_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// ── Request interceptor: attach JWT ───────────────────────────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ── Response interceptor: handle 401 ─────────────────────────────────────────
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default api;

// ── Typed API helpers ─────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Document {
  id: string;
  owner_id: string;
  filename: string;
  original_filename: string;
  file_type: "pdf" | "audio" | "video";
  file_size: number;
  status: "pending" | "processing" | "ready" | "error";
  error_message?: string;
  duration_seconds?: number;
  summary?: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListOut {
  items: Document[];
  total: number;
}

export interface ChatSession {
  id: string;
  user_id: string;
  document_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatHistoryOut {
  session: ChatSession;
  messages: ChatMessage[];
}

export interface TimestampEntry {
  start: number;
  end: number;
  text: string;
  relevance: number;
}

export interface TimestampResponse {
  document_id: string;
  query: string;
  timestamps: TimestampEntry[];
}

// Auth
export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post<User>("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post<{ access_token: string; token_type: string }>("/auth/login", data),
  me: () => api.get<User>("/auth/me"),
};

// Documents
export const documentsApi = {
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post<Document>("/documents/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    });
  },
  list: (skip = 0, limit = 20) =>
    api.get<DocumentListOut>("/documents", { params: { skip, limit } }),
  get: (id: string) => api.get<Document>(`/documents/${id}`),
  delete: (id: string) => api.delete(`/documents/${id}`),
  summarize: (id: string) =>
    api.post<{ document_id: string; summary: string }>(`/documents/${id}/summarize`),
  timestamps: (id: string, query: string, top_k = 5) =>
    api.get<TimestampResponse>(`/documents/${id}/timestamps`, { params: { query, top_k } }),
  presignedUrl: (id: string) =>
    api.get<{ url: string }>(`/documents/${id}/presigned-url`),
};

// Chat
export const chatApi = {
  sessions: (docId: string) => api.get<ChatSession[]>(`/chat/${docId}/sessions`),
  history: (sessionId: string) =>
    api.get<ChatHistoryOut>(`/chat/sessions/${sessionId}/history`),
  deleteSession: (sessionId: string) =>
    api.delete(`/chat/sessions/${sessionId}`),
};

import axios from "axios";
import { getAuthToken, clearAuthSession, isTokenExpired } from "./auth";

const api = axios.create({
  baseURL: "http://localhost:8000",
  // Let axios set Content-Type automatically for FormData
  headers: {},
  // Increased timeout for slow AI responses (3 minutes)
  timeout: 180000,
});

api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuthSession();
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

export interface DocumentOut {
  id: number;
  filename: string;
  category: string;
  source: string;
  status: string;
  summary?: string;
  preview?: any;
  metadata?: any;
  analytics?: any;
  page_count?: number;
  chunk_count?: number;
  uploaded_at: string;
}

export interface ChatResponse {
  answer: string;
  sources: { filename: string; page_number?: number }[];
  confidence?: string;
  conversation_id?: number;
}

export const documentApi = {
  uploadFiles: (files: File[], category: string, source: string) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('category', category);
    formData.append('source', source);
    return api.post('/upload/files', formData);
  },
  getDocumentList: () => api.get<DocumentOut[]>('/documents/list'),
  getDocument: (id: number) => api.get<DocumentOut>(`/documents/${id}`),
  deleteDocument: (id: number) => api.delete(`/documents/${id}`),
  getStats: () => api.get<any>('/documents/stats'),
};

export const chatApi = {
  queryChat: (query: string, conversation_id?: number) => 
    api.post<ChatResponse>('/chat/query', { query, conversation_id }),
  queryWithFile: (query: string, file: File) => {
    const formData = new FormData();
    formData.append('query', query);
    formData.append('file', file);
    return api.post<ChatResponse>('/chat/query-with-file', formData);
  },
  getConversations: () => api.get<any[]>('/chat/conversations'),
  getConversation: (id: number) => api.get<any>(`/chat/conversation/${id}`),
  deleteConversation: (id: number) => api.delete(`/chat/conversation/${id}`),
};

export default api;

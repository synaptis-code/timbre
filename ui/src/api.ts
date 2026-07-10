/** Client de l'API REST locale (conversations, historique, réglages). */

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://127.0.0.1:8765";

export interface ConversationMeta {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  interrupted: boolean;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`API ${path} : ${response.status} ${response.statusText}`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const api = {
  listConversations: () => request<ConversationMeta[]>("/api/conversations"),
  createConversation: () => request<ConversationMeta>("/api/conversations", { method: "POST" }),
  renameConversation: (id: string, title: string) =>
    request<ConversationMeta>(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteConversation: (id: string) =>
    request<void>(`/api/conversations/${id}`, { method: "DELETE" }),
  listMessages: (id: string) => request<StoredMessage[]>(`/api/conversations/${id}/messages`),
  getSettings: () => request<{ language: string }>("/api/settings"),
  putSettings: (language: string) =>
    request<{ language: string }>("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ language }),
    }),
};

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
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body: unknown = await response.json();
      if (typeof body === "object" && body !== null && "detail" in body) {
        detail = String((body as { detail: unknown }).detail);
      }
    } catch {
      // corps non-JSON : on garde le statut HTTP
    }
    throw new Error(detail);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export interface ProviderInfo {
  id: string;
  name: string;
  local: boolean;
  needs_key: boolean;
  base_url: string;
  model: string | null;
  has_key: boolean;
}

export interface ProvidersState {
  active: string;
  providers: ProviderInfo[];
}

export interface Persona {
  id: string;
  name: string;
  language: string;
  system_prompt: string;
  voice: { engine: string; voice_id: string; params: { rate: number; pitch: number } };
  greeting: string;
  temperature: number;
}

export interface PersonaPayload {
  name: string;
  system_prompt: string;
  voice_id: string;
  rate: number;
  pitch: number;
  greeting: string;
  temperature: number;
}

export interface VoiceOption {
  id: string;
  label: string;
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
  getProviders: () => request<ProvidersState>("/api/providers"),
  updateProvider: (id: string, config: { api_key?: string; base_url?: string; model?: string }) =>
    request<ProvidersState>(`/api/providers/${id}`, {
      method: "PUT",
      body: JSON.stringify(config),
    }),
  setActiveProvider: (id: string) =>
    request<ProvidersState>("/api/providers/active", {
      method: "PUT",
      body: JSON.stringify({ provider: id }),
    }),
  listProviderModels: (id: string) =>
    request<{ models: string[] }>(`/api/providers/${id}/models`),
  listPersonas: () => request<Persona[]>("/api/personas"),
  createPersona: (payload: PersonaPayload) =>
    request<Persona>("/api/personas", { method: "POST", body: JSON.stringify(payload) }),
  updatePersona: (id: string, payload: PersonaPayload) =>
    request<Persona>(`/api/personas/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deletePersona: (id: string) => request<void>(`/api/personas/${id}`, { method: "DELETE" }),
  listVoices: () => request<VoiceOption[]>("/api/voices"),
  getSettings: () => request<{ language: string }>("/api/settings"),
  putSettings: (language: string) =>
    request<{ language: string }>("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ language }),
    }),
};

// Miroir TypeScript de src/timbre/protocol/ (backend).
// Verrouillé par le snapshot schemas/ws-protocol.schema.json : si le backend
// change, le test test_schema_snapshot.py échoue et ce fichier doit être mis à jour.

export type AppState = "idle" | "listening" | "thinking" | "speaking";

// Client → serveur
export interface UserMessage {
  type: "user_message";
  text: string;
  /** Capture d'écran du tour (data-URL JPEG), si le partage est actif. */
  image?: string;
}
export interface UserAudio {
  type: "user_audio";
  audio_b64: string;
  format: "wav";
  image?: string;
}
export interface Interrupt {
  type: "interrupt";
}
export interface SetPersona {
  type: "set_persona";
  persona_id: string;
  greet?: boolean;
}
export interface ListPersonas {
  type: "list_personas";
}
export interface SetAsrDevice {
  type: "set_asr_device";
  device: "cuda" | "cpu";
}
export type ClientMessage =
  | UserMessage
  | UserAudio
  | Interrupt
  | SetPersona
  | ListPersonas
  | SetAsrDevice;

// Serveur → client
export interface AiChunk {
  type: "ai_chunk";
  text: string;
  last: boolean;
  interrupted: boolean;
}
export interface StateChange {
  type: "state_change";
  state: AppState;
}
export interface ErrorMessage {
  type: "error";
  code: string;
  message: string;
}
export interface ModelInfo {
  type: "model_info";
  model: string;
}
export interface AiAudio {
  type: "ai_audio";
  audio_b64: string;
  format: "mp3" | "wav";
  text: string;
}
export interface UserTranscript {
  type: "user_transcript";
  text: string;
}
export interface PersonaSummary {
  id: string;
  name: string;
  valid: boolean;
  error: string | null;
}
export interface PersonaList {
  type: "persona_list";
  personas: PersonaSummary[];
  active: string;
}
export interface AsrInfo {
  type: "asr_info";
  device: string;
}
export interface TurnMetrics {
  type: "turn_metrics";
  asr_ms: number | null;
  first_token_ms: number | null;
  first_audio_ms: number | null;
  total_ms: number;
  vram_used_mb: number | null;
  vram_total_mb: number | null;
}
export type ServerMessage =
  | AiChunk
  | StateChange
  | ErrorMessage
  | ModelInfo
  | AiAudio
  | UserTranscript
  | PersonaList
  | AsrInfo
  | TurnMetrics;

const SERVER_MESSAGE_TYPES = new Set([
  "ai_chunk",
  "state_change",
  "error",
  "model_info",
  "ai_audio",
  "user_transcript",
  "persona_list",
  "asr_info",
  "turn_metrics",
]);

export function parseServerMessage(raw: string): ServerMessage | null {
  try {
    const data: unknown = JSON.parse(raw);
    if (
      typeof data === "object" &&
      data !== null &&
      "type" in data &&
      SERVER_MESSAGE_TYPES.has((data as { type: string }).type)
    ) {
      return data as ServerMessage;
    }
  } catch {
    // JSON invalide : traité comme message inconnu ci-dessous.
  }
  console.error("Message serveur inconnu ou illisible :", raw);
  return null;
}

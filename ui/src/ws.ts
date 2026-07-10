import type { ClientMessage, ServerMessage } from "./protocol";
import { parseServerMessage } from "./protocol";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export interface TimbreSocketHandlers {
  onMessage: (message: ServerMessage) => void;
  onStatus: (status: ConnectionStatus) => void;
}

export const WS_BASE =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? "ws://127.0.0.1:8765/ws";
const DEFAULT_URL = WS_BASE;
const RECONNECT_MIN_MS = 500;
const RECONNECT_MAX_MS = 5000;

/** Client WebSocket avec reconnexion automatique (backoff exponentiel plafonné). */
export class TimbreSocket {
  private readonly handlers: TimbreSocketHandlers;
  private readonly url: string;
  private ws: WebSocket | null = null;
  private reconnectDelay = RECONNECT_MIN_MS;
  private reconnectTimer: number | null = null;
  private disposed = false;

  constructor(handlers: TimbreSocketHandlers, url?: string) {
    this.handlers = handlers;
    this.url = url ?? (import.meta.env.VITE_WS_URL as string | undefined) ?? DEFAULT_URL;
    this.connect();
  }

  private connect(): void {
    if (this.disposed) return;
    this.handlers.onStatus("connecting");
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectDelay = RECONNECT_MIN_MS;
      this.handlers.onStatus("connected");
    };
    this.ws.onmessage = (event: MessageEvent<string>) => {
      const message = parseServerMessage(event.data);
      if (message !== null) this.handlers.onMessage(message);
    };
    this.ws.onclose = () => {
      this.ws = null;
      this.handlers.onStatus("disconnected");
      this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      // onclose suit toujours onerror : la reconnexion y est déjà gérée.
    };
  }

  private scheduleReconnect(): void {
    if (this.disposed || this.reconnectTimer !== null) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS);
  }

  send(message: ClientMessage): boolean {
    if (this.ws === null || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(message));
    return true;
  }

  dispose(): void {
    this.disposed = true;
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
    this.ws?.close();
  }
}

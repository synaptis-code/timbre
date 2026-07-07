import { useEffect, useRef, useState } from "react";
import { AudioQueue } from "./audio";
import { ActionBar } from "./components/ActionBar";
import { ChatThread, type ChatMessage } from "./components/ChatThread";
import { StateIndicator } from "./components/StateIndicator";
import { MicController } from "./mic";
import type { AppState, ServerMessage } from "./protocol";
import { TimbreSocket, type ConnectionStatus } from "./ws";

export default function App() {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [appState, setAppState] = useState<AppState>("idle");
  const [modelName, setModelName] = useState<string | null>(null);
  const [micOn, setMicOn] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const socketRef = useRef<TimbreSocket | null>(null);
  const micRef = useRef<MicController | null>(null);
  const nextId = useRef(0);

  useEffect(() => {
    const append = (message: Omit<ChatMessage, "id">) => {
      setMessages((prev) => [...prev, { ...message, id: nextId.current++ }]);
    };

    const mic = new MicController({
      onSpeech: (wavB64) => {
        socketRef.current?.send({ type: "user_audio", audio_b64: wavB64, format: "wav" });
      },
      onStatus: setMicOn,
      onError: (message) => append({ role: "error", text: message }),
    });
    micRef.current = mic;

    // Anti-feedback : micro en pause pendant que l'IA parle (bug n°8).
    const audioQueue = new AudioQueue((active) => mic.setTtsPlaying(active));

    const handleMessage = (message: ServerMessage) => {
      switch (message.type) {
        case "state_change":
          setAppState(message.state);
          break;
        case "model_info":
          setModelName(message.model);
          break;
        case "user_transcript":
          append({ role: "user", text: message.text });
          break;
        case "ai_audio":
          audioQueue.enqueue(message.audio_b64);
          break;
        case "ai_chunk":
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last !== undefined && last.role === "ai" && last.streaming) {
              const updated: ChatMessage = {
                ...last,
                text: last.text + message.text,
                streaming: !message.last,
              };
              return [...prev.slice(0, -1), updated];
            }
            return [
              ...prev,
              { id: nextId.current++, role: "ai", text: message.text, streaming: !message.last },
            ];
          });
          break;
        case "error":
          append({ role: "error", text: `${message.code} — ${message.message}` });
          break;
      }
    };

    const socket = new TimbreSocket({ onMessage: handleMessage, onStatus: setStatus });
    socketRef.current = socket;
    return () => {
      socket.dispose();
      audioQueue.stop();
      mic.destroy();
    };
  }, []);

  const sendUserMessage = (text: string) => {
    const sent = socketRef.current?.send({ type: "user_message", text }) ?? false;
    if (sent) {
      setMessages((prev) => [...prev, { id: nextId.current++, role: "user", text }]);
    }
  };

  // « En écoute » est un état d'affichage : micro ouvert et rien en cours côté backend.
  const displayState: AppState = appState === "idle" && micOn ? "listening" : appState;

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Timbre</h1>
        {modelName !== null && <span className="model-badge">{modelName}</span>}
        <span className={`connection connection--${status}`}>
          {status === "connected"
            ? "Connecté"
            : status === "connecting"
              ? "Connexion…"
              : "Déconnecté — reconnexion…"}
        </span>
      </header>
      <StateIndicator state={displayState} />
      <ChatThread messages={messages} />
      <ActionBar
        disabled={status !== "connected"}
        micOn={micOn}
        onToggleMic={() => void micRef.current?.toggle()}
        onSend={sendUserMessage}
      />
    </div>
  );
}

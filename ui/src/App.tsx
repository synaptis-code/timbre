import { useEffect, useRef, useState } from "react";
import { ActionBar } from "./components/ActionBar";
import { ChatThread, type ChatMessage } from "./components/ChatThread";
import { StateIndicator } from "./components/StateIndicator";
import type { AppState, ServerMessage } from "./protocol";
import { TimbreSocket, type ConnectionStatus } from "./ws";

export default function App() {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [appState, setAppState] = useState<AppState>("idle");
  const [modelName, setModelName] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const socketRef = useRef<TimbreSocket | null>(null);
  const nextId = useRef(0);

  useEffect(() => {
    const handleMessage = (message: ServerMessage) => {
      switch (message.type) {
        case "state_change":
          setAppState(message.state);
          break;
        case "model_info":
          setModelName(message.model);
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
          setMessages((prev) => [
            ...prev,
            { id: nextId.current++, role: "error", text: `${message.code} — ${message.message}` },
          ]);
          break;
      }
    };

    const socket = new TimbreSocket({ onMessage: handleMessage, onStatus: setStatus });
    socketRef.current = socket;
    return () => socket.dispose();
  }, []);

  const sendUserMessage = (text: string) => {
    const sent = socketRef.current?.send({ type: "user_message", text }) ?? false;
    if (sent) {
      setMessages((prev) => [...prev, { id: nextId.current++, role: "user", text }]);
    }
  };

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
      <StateIndicator state={appState} />
      <ChatThread messages={messages} />
      <ActionBar disabled={status !== "connected"} onSend={sendUserMessage} />
    </div>
  );
}

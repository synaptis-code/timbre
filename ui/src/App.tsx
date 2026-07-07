import { useEffect, useRef, useState } from "react";
import { AudioQueue } from "./audio";
import { ActionBar } from "./components/ActionBar";
import { ChatThread, type ChatMessage } from "./components/ChatThread";
import { StateIndicator } from "./components/StateIndicator";
import { MicController } from "./mic";
import { ScreenShare } from "./screen";
import { PersonaSelect } from "./components/PersonaSelect";
import type { AppState, PersonaSummary, ServerMessage } from "./protocol";
import { TimbreSocket, type ConnectionStatus } from "./ws";

export default function App() {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [appState, setAppState] = useState<AppState>("idle");
  const [modelName, setModelName] = useState<string | null>(null);
  const [micOn, setMicOn] = useState(false);
  const [screenOn, setScreenOn] = useState(false);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [personas, setPersonas] = useState<PersonaSummary[]>([]);
  const [activePersona, setActivePersona] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const socketRef = useRef<TimbreSocket | null>(null);
  const micRef = useRef<MicController | null>(null);
  const screenRef = useRef<ScreenShare | null>(null);
  const audioRef = useRef<AudioQueue | null>(null);
  const nextId = useRef(0);

  useEffect(() => {
    const append = (message: Omit<ChatMessage, "id">) => {
      setMessages((prev) => [...prev, { ...message, id: nextId.current++ }]);
    };

    const screen = new ScreenShare({
      onStatus: setScreenOn,
      onError: (message) => append({ role: "error", text: message }),
    });
    screenRef.current = screen;

    const mic = new MicController({
      onSpeech: (wavB64) => {
        const image = screen.isOn ? screen.captureFrame() : null;
        socketRef.current?.send({
          type: "user_audio",
          audio_b64: wavB64,
          format: "wav",
          ...(image !== null ? { image } : {}),
        });
      },
      onStatus: setMicOn,
      onError: (message) => append({ role: "error", text: message }),
    });
    micRef.current = mic;

    // Anti-feedback : micro en pause pendant que l'IA parle (bug n°8), et
    // l'indicateur « Parle » suit la lecture réelle, pas l'envoi des données.
    const audioQueue = new AudioQueue((active) => {
      mic.setTtsPlaying(active);
      setTtsPlaying(active);
    });
    audioRef.current = audioQueue;

    const handleMessage = (message: ServerMessage) => {
      switch (message.type) {
        case "state_change":
          setAppState(message.state);
          break;
        case "model_info":
          setModelName(message.model);
          break;
        case "persona_list":
          setPersonas(message.personas);
          setActivePersona(message.active);
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
                interrupted: message.interrupted || undefined,
              };
              return [...prev.slice(0, -1), updated];
            }
            if (message.text === "" && message.last) return prev; // clôture sans bulle
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
      screen.stop();
    };
  }, []);

  const sendUserMessage = (text: string) => {
    const screen = screenRef.current;
    const image = screen !== null && screen.isOn ? screen.captureFrame() : null;
    const sent =
      socketRef.current?.send({
        type: "user_message",
        text,
        ...(image !== null ? { image } : {}),
      }) ?? false;
    if (sent) {
      setMessages((prev) => [
        ...prev,
        { id: nextId.current++, role: "user", text, withImage: image !== null },
      ]);
    }
  };

  const stopTurn = () => {
    audioRef.current?.stop();
    socketRef.current?.send({ type: "interrupt" });
  };

  // État affiché : « Parle » suit la lecture audio réelle côté client ;
  // « En écoute » = micro ouvert et rien en cours.
  const displayState: AppState = ttsPlaying
    ? "speaking"
    : appState === "idle" && micOn
      ? "listening"
      : appState;
  const canStop = ttsPlaying || appState === "thinking" || appState === "speaking";

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Timbre</h1>
        {modelName !== null && <span className="model-badge">{modelName}</span>}
        <PersonaSelect
          personas={personas}
          active={activePersona}
          disabled={status !== "connected"}
          onSelect={(id) => socketRef.current?.send({ type: "set_persona", persona_id: id })}
          onRefresh={() => socketRef.current?.send({ type: "list_personas" })}
        />
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
        screenOn={screenOn}
        canStop={canStop}
        onToggleMic={() => void micRef.current?.toggle()}
        onToggleScreen={() => void screenRef.current?.toggle()}
        onStop={stopTurn}
        onSend={sendUserMessage}
      />
    </div>
  );
}

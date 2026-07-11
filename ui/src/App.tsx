import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ConversationMeta } from "./api";
import { AudioQueue } from "./audio";
import { ChatThread, type ChatMessage } from "./components/ChatThread";
import { Composer } from "./components/Composer";
import { PersonaSelect } from "./components/PersonaSelect";
import { SettingsView } from "./components/SettingsView";
import { Sidebar } from "./components/Sidebar";
import { StateIndicator } from "./components/StateIndicator";
import { MicController } from "./mic";
import type { AppState, PersonaSummary, ServerMessage, TurnMetrics } from "./protocol";
import { ScreenShare } from "./screen";
import { TimbreSocket, WS_BASE, type ConnectionStatus } from "./ws";

export default function App() {
  const [view, setView] = useState<"chat" | "settings">("chat");
  const [conversations, setConversations] = useState<ConversationMeta[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [appState, setAppState] = useState<AppState>("idle");
  const [modelName, setModelName] = useState<string | null>(null);
  const [micOn, setMicOn] = useState(false);
  const [screenOn, setScreenOn] = useState(false);
  const [ttsPlaying, setTtsPlaying] = useState(false);
  const [personas, setPersonas] = useState<PersonaSummary[]>([]);
  const [activePersona, setActivePersona] = useState("");
  const [metrics, setMetrics] = useState<TurnMetrics | null>(null);
  const [asrDevice, setAsrDevice] = useState<string | null>(null);
  const [language, setLanguage] = useState("fr");
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const socketRef = useRef<TimbreSocket | null>(null);
  const micRef = useRef<MicController | null>(null);
  const screenRef = useRef<ScreenShare | null>(null);
  const audioRef = useRef<AudioQueue | null>(null);
  const nextId = useRef(0);
  const bootstrapped = useRef(false);

  const append = useCallback((message: Omit<ChatMessage, "id">) => {
    setMessages((prev) => [...prev, { ...message, id: nextId.current++ }]);
  }, []);

  const refreshConversations = useCallback(async () => {
    setConversations(await api.listConversations());
  }, []);

  // ── Périphériques (créés une seule fois) ─────────────────────────────────
  useEffect(() => {
    const audioQueue = new AudioQueue((active) => setTtsPlaying(active));
    audioRef.current = audioQueue;

    const screen = new ScreenShare({
      onStatus: setScreenOn,
      onError: (message) => append({ role: "error", text: message }),
    });
    screenRef.current = screen;

    // Barge-in : début de parole → pause de la voix ; faux départ → reprise ;
    // vraie phrase → lecture coupée, la prise de parole remplace le tour.
    let bargedIn = false;
    const mic = new MicController({
      onSpeechStart: () => {
        if (audioQueue.isActive) {
          audioQueue.pause();
          bargedIn = true;
        }
      },
      onMisfire: () => {
        if (bargedIn) {
          audioQueue.resume();
          bargedIn = false;
        }
      },
      onSpeech: (wavB64) => {
        if (bargedIn) {
          audioQueue.stop();
          bargedIn = false;
        }
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

    return () => {
      mic.destroy();
      screen.stop();
      audioQueue.stop();
    };
  }, [append]);

  // ── Amorçage : conversations + réglages ─────────────────────────────────
  useEffect(() => {
    // Garde StrictMode : l'effet ne doit créer la conversation qu'une fois.
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    void (async () => {
      try {
        let list = await api.listConversations();
        if (list.length === 0) list = [await api.createConversation()];
        setConversations(list);
        setActiveId((prev) => prev ?? list[0].id);
        setLanguage((await api.getSettings()).language);
      } catch (error) {
        append({
          role: "error",
          text: `Backend injoignable : ${error instanceof Error ? error.message : String(error)}`,
        });
      }
    })();
  }, [append]);

  // ── Socket par conversation active ──────────────────────────────────────
  useEffect(() => {
    if (activeId === null) return;
    let cancelled = false;
    setMessages([]);
    void api
      .listMessages(activeId)
      .then((stored) => {
        if (cancelled) return;
        setMessages(
          stored.map((message) => ({
            id: nextId.current++,
            role: message.role === "user" ? ("user" as const) : ("ai" as const),
            text: message.content,
            interrupted: message.interrupted || undefined,
          })),
        );
      })
      .catch(() => undefined);

    const handleMessage = (message: ServerMessage) => {
      switch (message.type) {
        case "state_change":
          setAppState(message.state);
          if (message.state === "idle") void refreshConversations().catch(() => undefined);
          break;
        case "model_info":
          setModelName(message.model);
          break;
        case "persona_list":
          setPersonas(message.personas);
          setActivePersona(message.active);
          break;
        case "turn_metrics":
          setMetrics(message);
          break;
        case "asr_info":
          setAsrDevice(message.device);
          break;
        case "user_transcript":
          append({ role: "user", text: message.text });
          break;
        case "ai_audio":
          audioRef.current?.enqueue(message.audio_b64);
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

    const socket = new TimbreSocket(
      { onMessage: handleMessage, onStatus: setStatus },
      `${WS_BASE}?conversation=${activeId}`,
    );
    socketRef.current = socket;
    return () => {
      cancelled = true;
      socket.dispose();
      audioRef.current?.stop();
    };
  }, [activeId, append, refreshConversations]);

  // ── Actions ──────────────────────────────────────────────────────────────
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

  const newConversation = () => {
    void api
      .createConversation()
      .then((meta) => {
        setConversations((prev) => [meta, ...prev]);
        setActiveId(meta.id);
        setView("chat");
      })
      .catch((error: unknown) => append({ role: "error", text: String(error) }));
  };

  const deleteConversation = (id: string) => {
    const target = conversations.find((c) => c.id === id);
    if (!window.confirm(`Supprimer « ${target?.title ?? "cette conversation"} » ?`)) return;
    void api
      .deleteConversation(id)
      .then(async () => {
        let list = await api.listConversations();
        if (list.length === 0) list = [await api.createConversation()];
        setConversations(list);
        if (id === activeId) setActiveId(list[0].id);
      })
      .catch((error: unknown) => append({ role: "error", text: String(error) }));
  };

  const renameActive = () => {
    const current = conversations.find((c) => c.id === activeId);
    if (current === undefined || activeId === null) return;
    const title = window.prompt("Titre de la conversation :", current.title);
    if (title === null || title.trim() === "") return;
    void api
      .renameConversation(activeId, title.trim())
      .then(() => refreshConversations())
      .catch((error: unknown) => append({ role: "error", text: String(error) }));
  };

  const changeLanguage = (value: string) => {
    setLanguage(value);
    void api.putSettings(value).catch((error: unknown) =>
      append({ role: "error", text: String(error) }),
    );
  };

  // État affiché : « Parle » suit la lecture audio réelle côté client ;
  // « En écoute » = micro ouvert et rien en cours.
  const displayState: AppState = ttsPlaying
    ? "speaking"
    : appState === "idle" && micOn
      ? "listening"
      : appState;
  const canStop = ttsPlaying || appState === "thinking" || appState === "speaking";
  const activeTitle = conversations.find((c) => c.id === activeId)?.title ?? "";
  const personaName = personas.find((p) => p.id === activePersona)?.name ?? "Timbre";

  return (
    <div className="shell">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        filter={filter}
        status={status}
        onFilterChange={setFilter}
        onSelect={(id) => {
          setActiveId(id);
          setView("chat");
        }}
        onNew={newConversation}
        onDelete={deleteConversation}
        onOpenSettings={() => setView("settings")}
      />

      {view === "settings" ? (
        <SettingsView
          language={language}
          metrics={metrics}
          asrDevice={asrDevice}
          disabled={status !== "connected"}
          onLanguageChange={changeLanguage}
          onSetAsrDevice={(device) => socketRef.current?.send({ type: "set_asr_device", device })}
          onBack={() => setView("chat")}
        />
      ) : (
        <div className="chat">
          <header className="topbar">
            <button
              type="button"
              className="topbar-title"
              onClick={renameActive}
              title="Renommer la conversation"
            >
              {activeTitle}
            </button>
            <StateIndicator state={displayState} />
            <div className="topbar-right">
              <PersonaSelect
                personas={personas}
                active={activePersona}
                disabled={status !== "connected"}
                onSelect={(id) => socketRef.current?.send({ type: "set_persona", persona_id: id })}
                onRefresh={() => socketRef.current?.send({ type: "list_personas" })}
              />
              {modelName !== null && <span className="model-badge">{modelName}</span>}
            </div>
          </header>
          <ChatThread messages={messages} persona={personaName} />
          <div className="composer-zone">
            <Composer
              disabled={status !== "connected"}
              micOn={micOn}
              screenOn={screenOn}
              canStop={canStop}
              personas={personas}
              onToggleMic={() => void micRef.current?.toggle()}
              onToggleScreen={() => void screenRef.current?.toggle()}
              onStop={stopTurn}
              onSend={sendUserMessage}
              onInvokePersona={(id) =>
                socketRef.current?.send({ type: "set_persona", persona_id: id, greet: false })
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}

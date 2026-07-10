import { useState, type FormEvent } from "react";
import { MicIcon, ScreenIcon, SendIcon, StopIcon } from "../icons";

interface ComposerProps {
  disabled: boolean;
  micOn: boolean;
  screenOn: boolean;
  canStop: boolean;
  onToggleMic: () => void;
  onToggleScreen: () => void;
  onStop: () => void;
  onSend: (text: string) => void;
}

export function Composer({
  disabled,
  micOn,
  screenOn,
  canStop,
  onToggleMic,
  onToggleScreen,
  onStop,
  onSend,
}: ComposerProps) {
  const [draft, setDraft] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (text.length === 0) return;
    onSend(text);
    setDraft("");
  };

  return (
    <form className="composer" onSubmit={submit}>
      <button
        type="button"
        className={`icon-btn ${micOn ? "icon-btn--active" : ""}`}
        onClick={onToggleMic}
        disabled={disabled}
        aria-pressed={micOn}
        title={micOn ? "Couper le micro" : "Micro mains-libres"}
      >
        <MicIcon />
      </button>
      <button
        type="button"
        className={`icon-btn ${screenOn ? "icon-btn--active" : ""}`}
        onClick={onToggleScreen}
        disabled={disabled}
        aria-pressed={screenOn}
        title={screenOn ? "Arrêter le partage d'écran" : "Partager l'écran"}
      >
        <ScreenIcon />
      </button>
      <input
        className="composer-input"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={disabled ? "En attente du serveur…" : "Envoyer un message"}
        disabled={disabled}
        aria-label="Message"
      />
      <button
        type="button"
        className="icon-btn icon-btn--stop"
        onClick={onStop}
        disabled={disabled || !canStop}
        title="Interrompre la réponse"
      >
        <StopIcon />
      </button>
      <button
        className="icon-btn icon-btn--send"
        type="submit"
        disabled={disabled || draft.trim() === ""}
        title="Envoyer"
      >
        <SendIcon />
      </button>
    </form>
  );
}

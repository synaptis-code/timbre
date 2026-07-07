import { useState, type FormEvent } from "react";

interface ActionBarProps {
  disabled: boolean;
  micOn: boolean;
  screenOn: boolean;
  canStop: boolean;
  onToggleMic: () => void;
  onToggleScreen: () => void;
  onStop: () => void;
  onSend: (text: string) => void;
}

export function ActionBar({
  disabled,
  micOn,
  screenOn,
  canStop,
  onToggleMic,
  onToggleScreen,
  onStop,
  onSend,
}: ActionBarProps) {
  const [draft, setDraft] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (text.length === 0) return;
    onSend(text);
    setDraft("");
  };

  return (
    <form className="action-bar" onSubmit={submit}>
      <button
        type="button"
        className={`action-mic ${micOn ? "action-mic--on" : ""}`}
        onClick={onToggleMic}
        disabled={disabled}
        aria-pressed={micOn}
        title={micOn ? "Couper le micro" : "Activer le micro (mains-libres)"}
      >
        {micOn ? "Micro ●" : "Micro ○"}
      </button>
      <button
        type="button"
        className={`action-mic ${screenOn ? "action-mic--on" : ""}`}
        onClick={onToggleScreen}
        disabled={disabled}
        aria-pressed={screenOn}
        title={
          screenOn
            ? "Arrêter le partage d'écran"
            : "Partager l'écran (une capture par tour est envoyée à l'IA)"
        }
      >
        {screenOn ? "Écran ●" : "Écran ○"}
      </button>
      <button
        type="button"
        className="action-stop"
        onClick={onStop}
        disabled={disabled || !canStop}
        title="Interrompre la réponse en cours"
      >
        Stop
      </button>
      <input
        className="action-input"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder={disabled ? "En attente du serveur…" : "Écris un message…"}
        disabled={disabled}
        aria-label="Message"
      />
      <button className="action-send" type="submit" disabled={disabled || draft.trim() === ""}>
        Envoyer
      </button>
    </form>
  );
}

import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import type { PersonaSummary } from "../protocol";
import { MicIcon, ScreenIcon, SendIcon, StopIcon } from "../icons";

interface ComposerProps {
  disabled: boolean;
  micOn: boolean;
  screenOn: boolean;
  canStop: boolean;
  personas: PersonaSummary[];
  onToggleMic: () => void;
  onToggleScreen: () => void;
  onStop: () => void;
  onSend: (text: string) => void;
  onInvokePersona: (id: string) => void;
}

/** Détecte un `@fragment` en cours de frappe à la position du curseur. */
function mentionAt(text: string, caret: number): { query: string; start: number } | null {
  const before = text.slice(0, caret);
  const match = /(?:^|\s)@([\p{L}0-9-]*)$/u.exec(before);
  if (match === null) return null;
  return { query: match[1].toLowerCase(), start: caret - match[1].length - 1 };
}

export function Composer({
  disabled,
  micOn,
  screenOn,
  canStop,
  personas,
  onToggleMic,
  onToggleScreen,
  onStop,
  onSend,
  onInvokePersona,
}: ComposerProps) {
  const [draft, setDraft] = useState("");
  const [mention, setMention] = useState<{ query: string; start: number } | null>(null);
  const [highlight, setHighlight] = useState(0);

  const matches = useMemo(() => {
    if (mention === null) return [];
    return personas
      .filter((p) => p.valid && p.name.toLowerCase().includes(mention.query))
      .slice(0, 6);
  }, [mention, personas]);

  const updateDraft = (value: string, caret: number) => {
    setDraft(value);
    setMention(mentionAt(value, caret));
    setHighlight(0);
  };

  const pickPersona = (persona: PersonaSummary) => {
    onInvokePersona(persona.id);
    // Retire le `@fragment` en cours ; le persona devient l'interlocuteur.
    if (mention !== null) {
      const caret = mention.start + mention.query.length + 1;
      setDraft((prev) => prev.slice(0, mention.start) + prev.slice(caret));
    }
    setMention(null);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (text.length === 0) return;
    onSend(text);
    setDraft("");
    setMention(null);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (matches.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((h) => (h + 1) % matches.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((h) => (h - 1 + matches.length) % matches.length);
    } else if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      pickPersona(matches[highlight]);
    } else if (event.key === "Escape") {
      setMention(null);
    }
  };

  return (
    <form className="composer" onSubmit={submit}>
      {matches.length > 0 && (
        <ul className="mention-pop" role="listbox">
          {matches.map((persona, index) => (
            <li key={persona.id}>
              <button
                type="button"
                className={`mention-item ${index === highlight ? "mention-item--on" : ""}`}
                onMouseDown={(event) => {
                  event.preventDefault();
                  pickPersona(persona);
                }}
              >
                <span className="mention-at">@</span>
                {persona.name}
              </button>
            </li>
          ))}
        </ul>
      )}
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
        onChange={(event) => updateDraft(event.target.value, event.target.selectionStart ?? 0)}
        onKeyDown={onKeyDown}
        placeholder={disabled ? "En attente du serveur…" : "Envoyer un message — @ pour un persona"}
        disabled={disabled}
        aria-label="Message"
        autoComplete="off"
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

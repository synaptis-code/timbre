import { useState, type FormEvent } from "react";

interface ActionBarProps {
  disabled: boolean;
  onSend: (text: string) => void;
}

export function ActionBar({ disabled, onSend }: ActionBarProps) {
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

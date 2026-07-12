import { useState, useRef, type FormEvent } from "react";
import { MicIcon, PlusIcon, SendIcon, StopIcon, XIcon, HeadphonesIcon } from "../icons";
import { normalizeImageDataUrl } from "../image";

interface ComposerProps {
  disabled: boolean;
  micOn: boolean;
  canStop: boolean;
  onToggleMic: () => void;
  onStop: () => void;
  onSend: (text: string, image?: string | null) => void;
  onToggleVoiceAgent: () => void;
}

export function Composer({
  disabled,
  micOn,
  canStop,
  onToggleMic,
  onStop,
  onSend,
  onToggleVoiceAgent,
}: ComposerProps) {
  const [draft, setDraft] = useState("");
  const [imageDraft, setImageDraft] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (text.length === 0 && !imageDraft) return;
    // Le protocole exige un texte non vide : repli neutre pour une image seule.
    onSend(text.length === 0 ? "[Image]" : text, imageDraft);
    setDraft("");
    setImageDraft(null);
  };

  // Lit puis NORMALISE l'image (JPEG ≤ 1280 px) : le backend n'accepte que
  // JPEG/PNG/WebP ≤ 8 Mo — un GIF collé ou une grosse capture PNG seraient
  // rejetés avec une erreur cryptique sinon.
  const readImageFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const raw = (event.target?.result as string) || null;
      if (raw === null) return;
      void normalizeImageDataUrl(raw)
        .then(setImageDraft)
        .catch(() => setImageDraft(null));
    };
    reader.readAsDataURL(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    readImageFile(file);
    // reset input so the same file can be selected again
    e.target.value = "";
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const file = e.clipboardData.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) return;
    readImageFile(file);
    e.preventDefault();
  };


  return (
    <div className="composer-container">
      <form className="composer-form" onSubmit={submit}>
        {imageDraft && (
          <div className="composer-image-preview">
            <img src={imageDraft} alt="Aperçu" />
            <button
              type="button"
              className="composer-image-remove"
              onClick={() => setImageDraft(null)}
              title="Retirer l'image"
            >
              <XIcon size={10} />
            </button>
          </div>
        )}

        <input
          className="composer-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onPaste={handlePaste}
          placeholder={disabled ? "En attente du serveur…" : "Envoyer un message"}
          disabled={disabled}
          aria-label="Message"
          autoComplete="off"
        />

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/*"
          style={{ display: "none" }}
        />

        <div className="composer-actions">
          <div className="composer-actions-left">
            <button
              type="button"
              className="composer-action-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              title="Ajouter une image"
            >
              <PlusIcon size={20} />
            </button>
          </div>

          <div className="composer-actions-right">
            {canStop && (
              <button
                type="button"
                className="composer-action-btn composer-action-btn--stop"
                onClick={onStop}
                disabled={disabled}
                title="Interrompre la réponse"
              >
                <StopIcon size={17} />
              </button>
            )}
            <button
              type="button"
              className={`composer-action-btn ${micOn ? "composer-action-btn--mic-on" : ""}`}
              onClick={onToggleMic}
              disabled={disabled}
              aria-pressed={micOn}
              title={micOn ? "Couper le micro" : "Micro mains-libres"}
            >
              <MicIcon size={20} />
            </button>
            {draft.trim() === "" && !imageDraft ? (
              <button
                type="button"
                className="composer-send-btn composer-send-btn--voice"
                onClick={onToggleVoiceAgent}
                disabled={disabled}
                title="Démarrer l'agent vocal"
              >
                <HeadphonesIcon size={20} />
              </button>
            ) : (
              <button
                className="composer-send-btn"
                type="submit"
                disabled={disabled}
                title="Envoyer"
              >
                <SendIcon size={20} />
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}

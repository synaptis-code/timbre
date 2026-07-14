import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { KokoroTab } from "./KokoroTab";
import { PiperTab } from "./PiperTab";

type Category = "piper" | "kokoro" | "chatterbox";

const CATEGORIES: ReadonlyArray<readonly [Category, string, string]> = [
  ["kokoro", "Kokoro", "Léger · naturel"],
  ["piper", "Piper", "50 langues"],
  ["chatterbox", "Chatterbox", "Expressif · GPU"],
];

export function VoiceLibraryModal({
  onClose,
  onChanged,
}: {
  onClose: () => void;
  onChanged: () => void;
}) {
  const [category, setCategory] = useState<Category>("kokoro");

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-panel voice-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Bibliothèque de voix"
      >
        <div className="modal-head">
          <h2 className="modal-title">Bibliothèque de voix</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Fermer">
            ✕
          </button>
        </div>

        <div className="voice-tabs" role="tablist">
          {CATEGORIES.map(([id, label, hint]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={category === id}
              className={`voice-tab ${category === id ? "voice-tab--on" : ""}`}
              onClick={() => setCategory(id)}
            >
              <span className="voice-tab-name">{label}</span>
              <span className="voice-tab-hint">{hint}</span>
            </button>
          ))}
        </div>

        <div className="voice-modal-body">
          {category === "kokoro" && <KokoroTab onChanged={onChanged} />}
          {category === "piper" && <PiperTab onChanged={onChanged} />}
          {category === "chatterbox" && (
            <div className="tab-soon">
              <p className="tab-intro">
                Chatterbox — voix expressive avec émotions et clonage, ~25 langues. Plus lourd
                (GPU). Intégration en cours.
              </p>
              <span className="voice-badge voice-badge--warn">Bientôt</span>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

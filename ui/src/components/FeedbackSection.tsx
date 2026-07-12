import { useState } from "react";

const REPO_URL = "https://github.com/synaptis-code/timbre";
const CONTACT_EMAIL = "contact@synaptis.agency";
const APP_VERSION = "0.1.0";

type Kind = "bug" | "idee" | "autre";

const KINDS: ReadonlyArray<readonly [Kind, string, string]> = [
  ["bug", "Un bug", "[Bug]"],
  ["idee", "Une idée", "[Idée]"],
  ["autre", "Autre retour", "[Retour]"],
];

/** Réglages → Contact : envoyer un retour au développeur, sans compte ni
 * serveur intermédiaire — via une issue GitHub pré-remplie ou un e-mail. */
export function FeedbackSection() {
  const [kind, setKind] = useState<Kind>("bug");
  const [message, setMessage] = useState("");

  const prefix = KINDS.find(([id]) => id === kind)?.[2] ?? "[Retour]";
  const body = `${message.trim()}\n\n—\nTimbre ${APP_VERSION} · ${navigator.platform}`;

  const openIssue = () => {
    const url = `${REPO_URL}/issues/new?title=${encodeURIComponent(`${prefix} `)}&body=${encodeURIComponent(body)}`;
    window.open(url, "_blank", "noopener");
  };

  const openMail = () => {
    const url = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(`${prefix} Timbre`)}&body=${encodeURIComponent(body)}`;
    window.location.href = url;
  };

  return (
    <>
      <h1 className="settings-title">Contact</h1>
      <p className="settings-subtitle">
        Un bug, une idée, un avis sur Timbre ? Chaque retour aide vraiment le projet.
      </p>

      <section className="settings-card feedback-card">
        <div className="feedback-kinds" role="radiogroup" aria-label="Type de retour">
          {KINDS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`feedback-kind ${kind === id ? "feedback-kind--on" : ""}`}
              onClick={() => setKind(id)}
              aria-pressed={kind === id}
            >
              {label}
            </button>
          ))}
        </div>

        <textarea
          className="feedback-message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={6}
          placeholder={
            kind === "bug"
              ? "Décris le problème : ce que tu as fait, ce qui s'est passé, ce que tu attendais…"
              : "Dis-nous tout…"
          }
          aria-label="Message"
        />

        <div className="provider-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={openIssue}
            disabled={message.trim() === ""}
            title="Ouvre une issue GitHub pré-remplie (compte GitHub requis)"
          >
            Envoyer sur GitHub
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={openMail}
            disabled={message.trim() === ""}
            title={`Ouvre ton client mail vers ${CONTACT_EMAIL}`}
          >
            Envoyer par e-mail
          </button>
        </div>
        <p className="settings-hint">
          GitHub ouvre une issue publique pré-remplie ; l'e-mail passe par ton client de
          messagerie. Rien n'est envoyé sans ton action.
        </p>
      </section>
    </>
  );
}

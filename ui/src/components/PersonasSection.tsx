import { useEffect, useState } from "react";
import { api, type Persona, type PersonaPayload, type VoiceOption } from "../api";
import { PlusIcon, TrashIcon } from "../icons";

interface Draft extends PersonaPayload {
  id: string | null; // null = création
}

const EMPTY: Draft = {
  id: null,
  name: "",
  system_prompt:
    "Tu es …, un assistant vocal français. Tu réponds à l'oral, en phrases courtes et " +
    "naturelles, sans listes ni Markdown.",
  voice_id: "fr-FR-VivienneMultilingualNeural",
  rate: 1,
  pitch: 0,
  greeting: "",
  temperature: 0.8,
};

function toDraft(persona: Persona): Draft {
  return {
    id: persona.id,
    name: persona.name,
    system_prompt: persona.system_prompt,
    voice_id: persona.voice.voice_id,
    rate: persona.voice.params.rate,
    pitch: persona.voice.params.pitch,
    greeting: persona.greeting,
    temperature: persona.temperature,
  };
}

export function PersonasSection() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.listPersonas().then(setPersonas);

  useEffect(() => {
    void load().catch((error: unknown) => setFeedback({ kind: "error", text: String(error) }));
    void api.listVoices().then(setVoices).catch(() => undefined);
  }, []);

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((prev) => (prev === null ? prev : { ...prev, [key]: value }));

  const isDirty = () => {
    if (draft === null) return false;
    if (draft.id === null) {
      return (
        draft.name !== EMPTY.name ||
        draft.system_prompt !== EMPTY.system_prompt ||
        draft.voice_id !== EMPTY.voice_id ||
        draft.rate !== EMPTY.rate ||
        draft.pitch !== EMPTY.pitch ||
        draft.greeting !== EMPTY.greeting ||
        draft.temperature !== EMPTY.temperature
      );
    }
    const original = personas.find((p) => p.id === draft.id);
    if (!original) return false;
    const base = toDraft(original);
    return (
      draft.name !== base.name ||
      draft.system_prompt !== base.system_prompt ||
      draft.voice_id !== base.voice_id ||
      draft.rate !== base.rate ||
      draft.pitch !== base.pitch ||
      draft.greeting !== base.greeting ||
      draft.temperature !== base.temperature
    );
  };

  const save = () => {
    if (draft === null) return;
    const { id, ...payload } = draft;
    setBusy(true);
    setFeedback(null);
    const action = id === null ? api.createPersona(payload) : api.updatePersona(id, payload);
    void action
      .then(async () => {
        await load();
        setDraft(null);
      })
      .catch((error: unknown) =>
        setFeedback({
          kind: "error",
          text: error instanceof Error ? error.message : String(error),
        }),
      )
      .finally(() => setBusy(false));
  };

  const remove = (persona: Persona) => {
    if (!window.confirm(`Supprimer le persona « ${persona.name} » ?`)) return;
    void api
      .deletePersona(persona.id)
      .then(load)
      .catch((error: unknown) =>
        setFeedback({
          kind: "error",
          text: error instanceof Error ? error.message : String(error),
        }),
      );
  };

  if (draft !== null) {
    return (
      <>
        <h1 className="settings-title">{draft.id === null ? "Nouveau persona" : "Modifier"}</h1>
        <p className="settings-subtitle">
          Sa personnalité, sa voix et son message d'accueil.
        </p>
        <div className="persona-editor">
          <label className="provider-field">
            <span>Nom</span>
            <input
              value={draft.name}
              onChange={(event) => set("name", event.target.value)}
              placeholder="Léa, Coach, Docteur…"
              maxLength={48}
            />
          </label>
          <label className="provider-field">
            <span>Personnalité (prompt système)</span>
            <textarea
              className="persona-prompt"
              value={draft.system_prompt}
              onChange={(event) => set("system_prompt", event.target.value)}
              rows={5}
            />
          </label>
          <div className="persona-editor-row">
            <label className="provider-field">
              <span>Voix</span>
              <select value={draft.voice_id} onChange={(event) => set("voice_id", event.target.value)}>
                {voices.map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="provider-field persona-field-sm">
              <span>Débit · {draft.rate.toFixed(2)}</span>
              <input
                type="range"
                min={0.5}
                max={2}
                step={0.05}
                value={draft.rate}
                onChange={(event) => set("rate", Number(event.target.value))}
              />
            </label>
            <label className="provider-field persona-field-sm">
              <span>Hauteur · {draft.pitch > 0 ? `+${draft.pitch}` : draft.pitch} Hz</span>
              <input
                type="range"
                min={-50}
                max={50}
                step={1}
                value={draft.pitch}
                onChange={(event) => set("pitch", Number(event.target.value))}
              />
            </label>
          </div>
          <label className="provider-field">
            <span>Message d'accueil (optionnel)</span>
            <input
              value={draft.greeting}
              onChange={(event) => set("greeting", event.target.value)}
              placeholder="Salut ! Je t'écoute."
            />
          </label>
          <label className="provider-field persona-field-sm">
            <span>Créativité · {draft.temperature.toFixed(2)}</span>
            <input
              type="range"
              min={0}
              max={2}
              step={0.05}
              value={draft.temperature}
              onChange={(event) => set("temperature", Number(event.target.value))}
            />
          </label>

          <div className="provider-actions">
            <button type="button" className="btn-secondary" onClick={() => setDraft(null)}>
              Annuler
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={save}
              disabled={busy || draft.name.trim() === "" || !isDirty()}
            >
              Enregistrer
            </button>
          </div>
          {feedback?.kind === "error" && (
            <p className="provider-feedback provider-feedback--error">{feedback.text}</p>
          )}
        </div>
      </>
    );
  }

  return (
    <>
      <div className="settings-head-row">
        <div>
          <h1 className="settings-title">Personas</h1>
          <p className="settings-subtitle">
            Crée des personnalités avec leur voix.
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setDraft({ ...EMPTY })}>
          <PlusIcon size={16} />
          Nouveau
        </button>
      </div>

      {feedback?.kind === "ok" && (
        <p className="provider-feedback provider-feedback--ok">{feedback.text}</p>
      )}

      <div className="persona-list">
        {personas.map((persona) => (
          <div key={persona.id} className="persona-card">
            <button
              type="button"
              className="persona-card-main"
              onClick={() => setDraft(toDraft(persona))}
            >
              <strong>{persona.name}</strong>
              <span className="persona-card-prompt">{persona.system_prompt}</span>
            </button>
            <button
              type="button"
              className="persona-card-delete"
              onClick={() => remove(persona)}
              title="Supprimer"
              aria-label={`Supprimer ${persona.name}`}
            >
              <TrashIcon size={16} />
            </button>
          </div>
        ))}
      </div>
    </>
  );
}

import { useState } from "react";
import type { PersonaSummary } from "../protocol";
import { UserIcon, MicIcon, UploadIcon, XIcon } from "../icons";

interface VoiceAgentBarProps {
  micOn: boolean;
  screenOn: boolean;
  state: "idle" | "listening" | "thinking" | "speaking" | string;
  personas: PersonaSummary[];
  activePersona: string;
  onToggleMic: () => void;
  onToggleScreen: () => void;
  onInvokePersona: (id: string) => void;
  onClose: () => void;
}

export function VoiceAgentBar({
  micOn,
  screenOn,
  state,
  personas,
  activePersona,
  onToggleMic,
  onToggleScreen,
  onInvokePersona,
  onClose,
}: VoiceAgentBarProps) {
  const [personaMenuOpen, setPersonaMenuOpen] = useState(false);

  const activePersonaObj = personas.find((p) => p.id === activePersona);
  const isDefault = activePersona === "defaut";
  const activePersonaName = activePersonaObj ? activePersonaObj.name : "Timbre";

  return (
    <div className="voice-bar-container">
      {personaMenuOpen && (
        <div className="voice-persona-backdrop" onClick={() => setPersonaMenuOpen(false)} />
      )}

      {/* Bouton 1 : Sélection de Persona */}
      <div className="voice-persona-wrapper">
        <button
          type="button"
          className={`voice-bar-btn ${!isDefault ? "voice-bar-btn--persona" : ""} ${personaMenuOpen ? "voice-bar-btn--active" : ""}`}
          onClick={() => setPersonaMenuOpen(!personaMenuOpen)}
          title="Sélectionner le persona"
        >
          <UserIcon size={20} />
          {!isDefault && <span className="voice-bar-btn-text">{activePersonaName}</span>}
        </button>

        {personaMenuOpen && (
          <div className="voice-persona-dropdown">
            {personas.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`voice-persona-item ${p.id === activePersona ? "voice-persona-item--active" : ""}`}
                onClick={() => {
                  onInvokePersona(p.id);
                  setPersonaMenuOpen(false);
                }}
              >
                {p.id === "defaut" ? "Aucun" : p.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Bouton 2 : Partager l'écran */}
      <button
        type="button"
        className={`voice-bar-btn ${screenOn ? "voice-bar-btn--active" : ""}`}
        onClick={onToggleScreen}
        title={screenOn ? "Arrêter le partage d'écran" : "Partager l'écran"}
      >
        <UploadIcon size={20} />
      </button>

      {/* Centre : Capsule interactive */}
      <div className={`voice-capsule voice-capsule--${state}`} title={`Agent vocal : ${state}`}>
        <div className="voice-capsule-wave-container">
          <div className="voice-capsule-wave wave-1" />
          <div className="voice-capsule-wave wave-2" />
          <div className="voice-capsule-wave wave-3" />
        </div>
        <div className="voice-capsule-label">
          {state === "listening" ? "En écoute" : state === "thinking" ? "Réflexion" : state === "speaking" ? "Parle" : "Prêt"}
        </div>
      </div>

      {/* Bouton 4 : Microphone (Mute) */}
      <button
        type="button"
        className={`voice-bar-btn ${!micOn ? "voice-bar-btn--muted" : ""}`}
        onClick={onToggleMic}
        title={micOn ? "Couper le micro" : "Activer le micro"}
      >
        <MicIcon size={20} />
      </button>

      {/* Bouton 5 : Fermer */}
      <button
        type="button"
        className="voice-bar-btn voice-bar-btn--close"
        onClick={onClose}
        title="Fermer l'agent vocal"
      >
        <XIcon size={20} />
      </button>
    </div>
  );
}


import { useState } from "react";
import { BackIcon } from "../icons";
import type { TurnMetrics } from "../protocol";
import { ProvidersSection } from "./ProvidersSection";

interface SettingsViewProps {
  language: string;
  metrics: TurnMetrics | null;
  asrDevice: string | null;
  activePersona: string;
  disabled: boolean;
  onLanguageChange: (language: string) => void;
  onSetAsrDevice: (device: "cuda" | "cpu") => void;
  onBack: () => void;
}

type Category = "interface" | "providers" | "personas" | "diagnostic";

const CATEGORIES: ReadonlyArray<readonly [Category, string]> = [
  ["interface", "Interface"],
  ["providers", "Fournisseur d'IA"],
  ["personas", "Personas"],
  ["diagnostic", "Diagnostic"],
];

const LANGUAGES = [
  ["fr", "Français"],
  ["en", "English"],
  ["es", "Español"],
  ["de", "Deutsch"],
  ["it", "Italiano"],
] as const;

const ms = (value: number | null | undefined) => (value == null ? "—" : `${value} ms`);

export function SettingsView({
  language,
  metrics,
  asrDevice,
  activePersona,
  disabled,
  onLanguageChange,
  onSetAsrDevice,
  onBack,
}: SettingsViewProps) {
  const [category, setCategory] = useState<Category>("interface");

  return (
    <div className="settings-layout">
      <nav className="settings-nav" aria-label="Catégories de réglages">
        <button type="button" className="btn-ghost settings-nav-back" onClick={onBack}>
          <BackIcon size={16} />
          Retour
        </button>
        <p className="eyebrow settings-nav-eyebrow">Réglages</p>
        {CATEGORIES.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`settings-nav-item ${category === id ? "settings-nav-item--active" : ""}`}
            onClick={() => setCategory(id)}
            aria-current={category === id ? "page" : undefined}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="settings-content">
        {category === "interface" && (
          <>
            <h1 className="settings-title">Interface</h1>
            <section className="settings-card">
              <div className="settings-row">
                <div>
                  <p className="settings-label">Langue de l'interface</p>
                  <p className="settings-hint">La traduction de l'interface arrivera plus tard.</p>
                </div>
                <select
                  className="settings-select"
                  value={language}
                  onChange={(event) => onLanguageChange(event.target.value)}
                  aria-label="Langue"
                >
                  {LANGUAGES.map(([code, label]) => (
                    <option key={code} value={code}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </section>
          </>
        )}

        {category === "providers" && <ProvidersSection />}

        {category === "personas" && (
          <>
            <h1 className="settings-title">Personas</h1>
            <section className="color-block color-block--cream">
              <p className="eyebrow">Bientôt — V2.3</p>
              <h2 className="color-block-title">Créés ici, sans fichier</h2>
              <p className="color-block-body">
                Création et édition des personas directement dans cette page (personnalité,
                voix, accueil), et invocation dans la conversation avec «&nbsp;@&nbsp;».
                Persona actif&nbsp;: <strong>{activePersona || "Timbre"}</strong>.
              </p>
            </section>
          </>
        )}

        {category === "diagnostic" && (
          <>
            <h1 className="settings-title">Diagnostic</h1>
            <section className="settings-card">
              <h2 className="settings-card-title">Dernier tour</h2>
              <div className="diag-grid">
                <span>
                  ASR <strong>{ms(metrics?.asr_ms)}</strong>
                </span>
                <span>
                  1ᵉʳ token <strong>{ms(metrics?.first_token_ms)}</strong>
                </span>
                <span>
                  1ʳᵉ voix <strong>{ms(metrics?.first_audio_ms)}</strong>
                </span>
                <span>
                  Total <strong>{ms(metrics?.total_ms)}</strong>
                </span>
                <span>
                  VRAM{" "}
                  <strong>
                    {metrics?.vram_used_mb != null && metrics.vram_total_mb != null
                      ? `${(metrics.vram_used_mb / 1024).toFixed(1)} / ${(metrics.vram_total_mb / 1024).toFixed(1)} Go`
                      : "—"}
                  </strong>
                </span>
              </div>
              {asrDevice !== null && (
                <div className="settings-row">
                  <div>
                    <p className="settings-label">Transcription Whisper</p>
                    <p className="settings-hint">
                      Rechargée au tour suivant après un changement.
                    </p>
                  </div>
                  <select
                    className="settings-select"
                    value={asrDevice}
                    disabled={disabled}
                    onChange={(event) => onSetAsrDevice(event.target.value as "cuda" | "cpu")}
                    aria-label="Périphérique Whisper"
                  >
                    <option value="cuda">GPU (cuda)</option>
                    <option value="cpu">CPU</option>
                  </select>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

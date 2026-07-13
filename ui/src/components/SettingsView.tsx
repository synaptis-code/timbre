import type { TurnMetrics } from "../protocol";
import { FeedbackSection } from "./FeedbackSection";
import { PersonasSection } from "./PersonasSection";
import { ProvidersSection } from "./ProvidersSection";
import type { SettingsCategory as Category } from "./Sidebar";

interface SettingsViewProps {
  language: string;
  metrics: TurnMetrics | null;
  asrDevice: string | null;
  disabled: boolean;
  category: Category;
  onLanguageChange: (language: string) => void;
  onSetAsrDevice: (device: "cuda" | "cpu") => void;
}

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
  disabled,
  category,
  onLanguageChange,
  onSetAsrDevice,
}: SettingsViewProps) {
  return (
    <div className="settings-layout">
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

        {category === "personas" && <PersonasSection />}

        {category === "support" && (
          <>
            <h1 className="settings-title">Soutenir Timbre</h1>
            <p className="settings-subtitle">
              Timbre est gratuit, open source et local d'abord. Le meilleur moyen de le
              soutenir&nbsp;: une étoile sur GitHub et un peu de bouche-à-oreille.
            </p>
            <section className="color-block color-block--lime">
              <p className="eyebrow">Open source</p>
              <h2 className="color-block-title">Mets une étoile au projet</h2>
              <p className="color-block-body">
                Chaque étoile aide Timbre à être découvert par d'autres personnes qui
                cherchent un assistant vocal qui respecte leur vie privée. Tu peux aussi
                partager le projet, ouvrir des issues, ou contribuer au code.
              </p>
              <a
                className="btn-primary"
                href="https://github.com/synaptis-code/timbre"
                target="_blank"
                rel="noreferrer"
              >
                ⭐ Star sur GitHub
              </a>
            </section>
            <section className="settings-card">
              <h2 className="settings-card-title">Créé par Synaptis</h2>
              <p className="settings-hint" style={{ marginBottom: 14 }}>
                Timbre est conçu et développé par l'agence Synaptis — création d'outils et
                d'expériences IA.
              </p>
              <a
                className="btn-secondary"
                href="https://www.synaptis.agency"
                target="_blank"
                rel="noreferrer"
              >
                www.synaptis.agency
              </a>
            </section>
          </>
        )}

        {category === "feedback" && <FeedbackSection />}

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

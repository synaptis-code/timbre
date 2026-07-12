import type { TurnMetrics } from "../protocol";
import { PersonasSection } from "./PersonasSection";
import { ProvidersSection } from "./ProvidersSection";

type Category = "interface" | "providers" | "personas" | "diagnostic";

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

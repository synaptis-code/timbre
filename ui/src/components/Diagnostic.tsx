import type { TurnMetrics } from "../protocol";

interface DiagnosticProps {
  metrics: TurnMetrics | null;
  asrDevice: string | null;
  disabled: boolean;
  onSetAsrDevice: (device: "cuda" | "cpu") => void;
}

const ms = (value: number | null) => (value === null ? "—" : `${value} ms`);

/** Panneau repliable de diagnostic : latences du dernier tour (§14 du plan),
 * VRAM, et bascule Whisper CPU/GPU en un clic. */
export function Diagnostic({ metrics, asrDevice, disabled, onSetAsrDevice }: DiagnosticProps) {
  return (
    <details className="diag">
      <summary className="diag-summary">Diagnostic</summary>
      <div className="diag-body">
        <span title="Transcription Whisper (tours vocaux)">
          ASR <strong>{ms(metrics?.asr_ms ?? null)}</strong>
        </span>
        <span title="Premier token du LLM">
          1ᵉʳ token <strong>{ms(metrics?.first_token_ms ?? null)}</strong>
        </span>
        <span title="Première phrase audio prête">
          1ʳᵉ voix <strong>{ms(metrics?.first_audio_ms ?? null)}</strong>
        </span>
        <span title="Durée totale du tour">
          total <strong>{ms(metrics?.total_ms ?? null)}</strong>
        </span>
        <span title="Mémoire GPU (nvidia-smi)">
          VRAM{" "}
          <strong>
            {metrics?.vram_used_mb != null && metrics.vram_total_mb != null
              ? `${(metrics.vram_used_mb / 1024).toFixed(1)} / ${(metrics.vram_total_mb / 1024).toFixed(1)} Go`
              : "—"}
          </strong>
        </span>
        {asrDevice !== null && (
          <label className="diag-device">
            Whisper
            <select
              value={asrDevice}
              disabled={disabled}
              onChange={(event) => onSetAsrDevice(event.target.value as "cuda" | "cpu")}
              aria-label="Périphérique Whisper"
            >
              <option value="cuda">GPU (cuda)</option>
              <option value="cpu">CPU</option>
            </select>
          </label>
        )}
      </div>
    </details>
  );
}

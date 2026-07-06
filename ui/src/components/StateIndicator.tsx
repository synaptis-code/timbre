import type { AppState } from "../protocol";

const LABELS: Record<AppState, string> = {
  idle: "Inactif",
  listening: "En écoute",
  thinking: "Réflexion…",
  speaking: "Parle",
};

export function StateIndicator({ state }: { state: AppState }) {
  return (
    <div className={`state state--${state}`} role="status" aria-live="polite">
      <span className="state-dot" aria-hidden="true" />
      <span className="state-label">{LABELS[state]}</span>
    </div>
  );
}

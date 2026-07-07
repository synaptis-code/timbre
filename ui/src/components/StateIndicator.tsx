import type { AppState } from "../protocol";

const LABELS: Record<AppState, string> = {
  idle: "Inactif",
  listening: "En écoute",
  thinking: "Réflexion…",
  speaking: "Parle",
};

/** Indicateur central unique : un orbe dont la couleur et la respiration
 * suivent l'état — compréhensible en un coup d'œil (§4 du plan). */
export function StateIndicator({ state }: { state: AppState }) {
  return (
    <div className={`state state--${state}`} role="status" aria-live="polite">
      <span className="state-orb" aria-hidden="true" />
      <span className="state-label">{LABELS[state]}</span>
    </div>
  );
}

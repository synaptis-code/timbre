import type { PersonaSummary } from "../protocol";

interface PersonaSelectProps {
  personas: PersonaSummary[];
  active: string;
  disabled: boolean;
  onSelect: (personaId: string) => void;
  /** Appelé à l'ouverture : redemande la liste au serveur (rechargement à chaud). */
  onRefresh: () => void;
}

export function PersonaSelect({
  personas,
  active,
  disabled,
  onSelect,
  onRefresh,
}: PersonaSelectProps) {
  const activePersona = personas.find((p) => p.id === active);
  const invalidCount = personas.filter((p) => !p.valid).length;

  return (
    <span className="persona">
      <span
        className={`persona-dot ${invalidCount > 0 ? "persona-dot--warn" : "persona-dot--ok"}`}
        title={
          invalidCount > 0
            ? personas
                .filter((p) => !p.valid)
                .map((p) => `${p.id} : ${p.error ?? "invalide"}`)
                .join("\n")
            : "Tous les personas sont valides"
        }
        aria-hidden="true"
      />
      <select
        className="persona-select"
        value={activePersona !== undefined ? active : ""}
        disabled={disabled || personas.length === 0}
        onChange={(event) => onSelect(event.target.value)}
        onFocus={onRefresh}
        onPointerDown={onRefresh}
        aria-label="Persona"
      >
        {activePersona === undefined && <option value="">{active}</option>}
        {personas.map((persona) => (
          <option
            key={persona.id}
            value={persona.id}
            disabled={!persona.valid}
            title={persona.error ?? undefined}
          >
            {persona.valid ? persona.name : `⚠ ${persona.id} (invalide)`}
          </option>
        ))}
      </select>
    </span>
  );
}

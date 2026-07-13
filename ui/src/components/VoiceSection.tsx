interface EngineBadge {
  label: string;
  tone: "neutral" | "good" | "warn";
}

interface VoiceEngine {
  id: string;
  name: string;
  tagline: string;
  description: string;
  badges: EngineBadge[];
  status: "ready" | "soon";
}

const ENGINES: VoiceEngine[] = [
  {
    id: "edge-tts",
    name: "Vivienne",
    tagline: "La voix par défaut, prête à l'emploi",
    description:
      "Voix neurale de Microsoft, très naturelle et à faible latence. Elle est " +
      "multilingue (français, anglais, espagnol, allemand…). En contrepartie, la " +
      "synthèse se fait sur les serveurs de Microsoft — c'est notre seule exception " +
      "au « tout local » — et elle ne joue pas les émotions.",
    badges: [
      { label: "Cloud (Microsoft)", tone: "warn" },
      { label: "Multilingue", tone: "good" },
      { label: "Sans émotions", tone: "neutral" },
    ],
    status: "ready",
  },
  {
    id: "piper",
    name: "Piper",
    tagline: "100 % local, léger, hors-ligne",
    description:
      "Moteur entièrement local : les voix sont de petits fichiers (~30 Mo) qui " +
      "tournent en temps réel sur le processeur, sans carte graphique ni connexion. " +
      "Idéal pour la confidentialité, mais le rendu est un cran en dessous de " +
      "Vivienne et reste sans émotions.",
    badges: [
      { label: "100 % local", tone: "good" },
      { label: "Léger · CPU", tone: "good" },
      { label: "Moins expressif", tone: "neutral" },
    ],
    status: "soon",
  },
  {
    id: "orpheus",
    name: "Orpheus",
    tagline: "Voix expressive avec émotions",
    description:
      "Moteur local basé sur un LLM : il gère les émotions (rires, soupirs…) et " +
      "plusieurs voix, avec un rendu proche de l'humain. C'est le plus gourmand : " +
      "une carte NVIDIA est recommandée et les modèles pèsent plusieurs gigaoctets.",
    badges: [
      { label: "Émotions", tone: "good" },
      { label: "NVIDIA recommandée", tone: "warn" },
      { label: "Lourd", tone: "neutral" },
    ],
    status: "soon",
  },
];

export function VoiceSection() {
  return (
    <>
      <h1 className="settings-title">Voix</h1>
      <p className="settings-subtitle">
        Choisis le moteur de synthèse vocale. Chacun a ses compromis entre qualité,
        confidentialité et matériel requis. Vivienne est active par défaut.
      </p>

      <div className="voice-engines">
        {ENGINES.map((engine) => (
          <section key={engine.id} className="voice-engine">
            <div className="voice-engine-head">
              <div>
                <h2 className="voice-engine-name">{engine.name}</h2>
                <p className="voice-engine-tagline">{engine.tagline}</p>
              </div>
              {engine.status === "ready" ? (
                <span className="voice-engine-state voice-engine-state--active">Active</span>
              ) : (
                <span className="voice-engine-state">Bientôt</span>
              )}
            </div>

            <p className="voice-engine-desc">{engine.description}</p>

            <div className="voice-engine-badges">
              {engine.badges.map((badge) => (
                <span key={badge.label} className={`voice-badge voice-badge--${badge.tone}`}>
                  {badge.label}
                </span>
              ))}
            </div>

            {engine.status === "soon" && (
              <button type="button" className="btn-secondary" disabled>
                Installation à venir
              </button>
            )}
          </section>
        ))}
      </div>
    </>
  );
}

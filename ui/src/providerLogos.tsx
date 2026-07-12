/** Logos des fournisseurs : tuiles générées par code (aucune image embarquée),
 * couleur de marque + monogramme — reconnaissables et fidèles à l'esprit épuré. */

interface LogoStyle {
  bg: string;
  fg: string;
  mono: string;
}

const LOGOS: Record<string, LogoStyle> = {
  lmstudio: { bg: "#4f46e5", fg: "#fff", mono: "LM" },
  ollama: { bg: "#111", fg: "#fff", mono: "OL" },
  localai: { bg: "#2563eb", fg: "#fff", mono: "LA" },
  lemonade: { bg: "#f4c430", fg: "#111", mono: "LE" },
  openai: { bg: "#10a37f", fg: "#fff", mono: "AI" },
  anthropic: { bg: "#d97757", fg: "#fff", mono: "A" },
  gemini: { bg: "#1a73e8", fg: "#fff", mono: "G" },
  nim: { bg: "#76b900", fg: "#111", mono: "NV" },
  together: { bg: "#0f6fff", fg: "#fff", mono: "TA" },
  deepseek: { bg: "#4d6bfe", fg: "#fff", mono: "DS" },
  groq: { bg: "#f55036", fg: "#fff", mono: "GQ" },
  mistral: { bg: "#fa5310", fg: "#fff", mono: "MI" },
  openrouter: { bg: "#6467f2", fg: "#fff", mono: "OR" },
  xai: { bg: "#111", fg: "#fff", mono: "xAI" },
  perplexity: { bg: "#20808d", fg: "#fff", mono: "PP" },
  fireworks: { bg: "#7c3aed", fg: "#fff", mono: "FW" },
  sambanova: { bg: "#ee2a7b", fg: "#fff", mono: "SN" },
  cohere: { bg: "#39594d", fg: "#fff", mono: "CO" },
};

const FALLBACK: LogoStyle = { bg: "#666", fg: "#fff", mono: "?" };

export function ProviderLogo({ id, size = 34 }: { id: string; size?: number }) {
  const style = LOGOS[id] ?? FALLBACK;
  return (
    <span
      className="provider-logo"
      aria-hidden="true"
      style={{
        width: size,
        height: size,
        background: style.bg,
        color: style.fg,
        fontSize: style.mono.length > 2 ? size * 0.32 : size * 0.4,
      }}
    >
      {style.mono}
    </span>
  );
}

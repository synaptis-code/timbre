import {
  siAnthropic,
  siDeepseek,
  siGooglegemini,
  siLmstudio,
  siMistralai,
  siNvidia,
  siOllama,
  siOpenrouter,
  siPerplexity,
  siX,
  type SimpleIcon,
} from "simple-icons";

/** Vrais logos de marque (simple-icons, CC0) là où ils existent ; pour les
 * fournisseurs absents de la bibliothèque, une tuile monogramme sobre. */

const ICONS: Record<string, SimpleIcon> = {
  anthropic: siAnthropic,
  gemini: siGooglegemini,
  lmstudio: siLmstudio,
  ollama: siOllama,
  deepseek: siDeepseek,
  mistral: siMistralai,
  xai: siX,
  openrouter: siOpenrouter,
  perplexity: siPerplexity,
  nim: siNvidia,
};

// Fournisseurs sans logo dans simple-icons : monogramme + couleur de marque.
const MONO: Record<string, { text: string; color: string }> = {
  openai: { text: "AI", color: "#10a37f" },
  groq: { text: "groq", color: "#f55036" },
  together: { text: "TA", color: "#0f6fff" },
  fireworks: { text: "FW", color: "#7c3aed" },
  localai: { text: "LA", color: "#2563eb" },
  lemonade: { text: "LE", color: "#d4a017" },
  sambanova: { text: "SN", color: "#ee2a7b" },
  cohere: { text: "CO", color: "#39594d" },
};

export function ProviderLogo({ id, size = 34 }: { id: string; size?: number }) {
  const icon = ICONS[id];
  const mono = MONO[id] ?? { text: "?", color: "#666" };
  return (
    <span className="provider-logo" aria-hidden="true" style={{ width: size, height: size }}>
      {icon !== undefined ? (
        <svg
          viewBox="0 0 24 24"
          width={size * 0.58}
          height={size * 0.58}
          fill={`#${icon.hex}`}
          role="img"
        >
          <path d={icon.path} />
        </svg>
      ) : (
        <span
          className="provider-logo-mono"
          style={{ color: mono.color, fontSize: mono.text.length > 2 ? size * 0.28 : size * 0.4 }}
        >
          {mono.text}
        </span>
      )}
    </span>
  );
}

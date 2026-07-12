// Map from provider id to its logo image filename and extension
const LOGO_FILES: Record<string, string> = {
  openai: "openai.webp",
  anthropic: "anthropic.webp",
  gemini: "gemini.webp",
  lmstudio: "lmstudio.webp",
  ollama: "ollama.webp",
  deepseek: "deepseek.webp",
  mistral: "mistral.webp",
  xai: "xai.webp",
  openrouter: "openrouter.webp",
  perplexity: "perplexity.webp",
  groq: "groq.webp",
  together: "together.webp",
  fireworks: "fireworks.webp",
  localai: "localai.png",
  cohere: "cohere.webp",
  sambanova: "sambanova.webp",
  nim: "nim.webp",
};

// Fallbacks for any other providers
const MONO: Record<string, { text: string; color: string }> = {
  lemonade: { text: "LE", color: "#d4a017" },
};

export function ProviderLogo({ id, size = 34 }: { id: string; size?: number }) {
  const logoFile = LOGO_FILES[id];

  if (logoFile) {
    const isLocalAI = id === "localai";
    return (
      <span
        className="provider-logo"
        aria-hidden="true"
        style={{
          width: size,
          height: size,
          background: isLocalAI ? "var(--surface-soft)" : "transparent",
          borderColor: isLocalAI ? "var(--hairline)" : "transparent",
          padding: isLocalAI ? "2px" : "0",
        }}
      >
        <img
          src={`/logos/${logoFile}`}
          alt={id}
          style={{
            width: "100%",
            height: "100%",
            borderRadius: isLocalAI ? "var(--r-md)" : "50%",
            objectFit: isLocalAI ? "contain" : "cover",
          }}
        />
      </span>
    );
  }

  // Fallback
  if (id === "lemonade") {
    return (
      <span
        className="provider-logo"
        aria-hidden="true"
        style={{
          width: size,
          height: size,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: `${size * 0.65}px`,
          background: "transparent",
          border: "none",
        }}
      >
        🍋
      </span>
    );
  }

  const mono = MONO[id] ?? { text: id.substring(0, 2).toUpperCase(), color: "#666" };
  return (
    <span className="provider-logo" aria-hidden="true" style={{ width: size, height: size }}>
      <span
        className="provider-logo-mono"
        style={{ color: mono.color, fontSize: mono.text.length > 2 ? size * 0.28 : size * 0.4 }}
      >
        {mono.text}
      </span>
    </span>
  );
}


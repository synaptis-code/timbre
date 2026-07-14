/** Bouton ▶ d'aperçu d'une voix, partagé par toutes les catégories. */
export function PreviewButton({
  voiceId,
  previewing,
  onPreview,
}: {
  voiceId: string;
  previewing: string | null;
  onPreview: (id: string) => void;
}) {
  return (
    <button
      type="button"
      className="voice-preview-btn"
      onClick={() => onPreview(voiceId)}
      disabled={previewing !== null}
      title="Écouter un aperçu"
      aria-label="Écouter un aperçu de la voix"
    >
      {previewing === voiceId ? "…" : "▶"}
    </button>
  );
}

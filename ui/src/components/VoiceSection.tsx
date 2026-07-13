import { useCallback, useEffect, useRef, useState } from "react";
import { api, type PiperLibrary, type PiperVoiceInfo } from "../api";
import { previewVoice } from "../voicePreview";

function PreviewButton({
  voiceId,
  previewing,
  onPreview,
}: {
  voiceId: string;
  previewing: string | null;
  onPreview: (id: string) => void;
}) {
  const active = previewing === voiceId;
  return (
    <button
      type="button"
      className="voice-preview-btn"
      onClick={() => onPreview(voiceId)}
      disabled={previewing !== null}
      title="Écouter un aperçu"
      aria-label="Écouter un aperçu de la voix"
    >
      {active ? "…" : "▶"}
    </button>
  );
}

interface EngineBadge {
  label: string;
  tone: "neutral" | "good" | "warn";
}

const VIVIENNE_BADGES: EngineBadge[] = [
  { label: "Cloud (Microsoft)", tone: "warn" },
  { label: "Multilingue", tone: "good" },
  { label: "Sans émotions", tone: "neutral" },
];

const PIPER_BADGES: EngineBadge[] = [
  { label: "100 % local", tone: "good" },
  { label: "Léger · CPU", tone: "good" },
  { label: "Moins expressif", tone: "neutral" },
];

const ORPHEUS_BADGES: EngineBadge[] = [
  { label: "Émotions", tone: "good" },
  { label: "NVIDIA recommandée", tone: "warn" },
  { label: "Lourd", tone: "neutral" },
];

function Badges({ badges }: { badges: EngineBadge[] }) {
  return (
    <div className="voice-engine-badges">
      {badges.map((badge) => (
        <span key={badge.label} className={`voice-badge voice-badge--${badge.tone}`}>
          {badge.label}
        </span>
      ))}
    </div>
  );
}

const formatMo = (bytes: number) => `${Math.round(bytes / 1_000_000)} Mo`;

function PiperVoiceRow({
  voice,
  busy,
  previewing,
  onDownload,
  onDelete,
  onPreview,
}: {
  voice: PiperVoiceInfo;
  busy: boolean;
  previewing: string | null;
  onDownload: (id: string) => void;
  onDelete: (id: string) => void;
  onPreview: (id: string) => void;
}) {
  const percent =
    voice.status === "downloading" && voice.size_bytes > 0
      ? Math.min(100, Math.round((voice.received / voice.size_bytes) * 100))
      : 0;

  return (
    <div className="piper-voice">
      <div className="piper-voice-info">
        <span className="piper-voice-name">
          {voice.label}
          {voice.recommended && <span className="piper-voice-reco">recommandée</span>}
        </span>
        <span className="piper-voice-meta">{formatMo(voice.size_bytes)}</span>
      </div>

      {voice.status === "ready" && (
        <div className="piper-voice-action">
          <span className="piper-voice-ready">✓ Installée</span>
          <PreviewButton voiceId={voice.id} previewing={previewing} onPreview={onPreview} />
          <button
            type="button"
            className="piper-link-danger"
            onClick={() => onDelete(voice.id)}
            disabled={busy}
          >
            Supprimer
          </button>
        </div>
      )}

      {voice.status === "downloading" && (
        <div className="piper-progress">
          <div className="piper-progress-track">
            <div className="piper-progress-fill" style={{ width: `${percent}%` }} />
          </div>
          <span className="piper-progress-label">{percent}%</span>
        </div>
      )}

      {(voice.status === "available" || voice.status === "error") && (
        <div className="piper-voice-action">
          {voice.status === "error" && (
            <span className="piper-voice-error" title={voice.error ?? undefined}>
              Échec
            </span>
          )}
          <button
            type="button"
            className="btn-secondary btn-compact"
            onClick={() => onDownload(voice.id)}
            disabled={busy}
          >
            {voice.status === "error" ? "Réessayer" : "Télécharger"}
          </button>
        </div>
      )}
    </div>
  );
}

export function VoiceSection() {
  const [piper, setPiper] = useState<PiperLibrary | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const preview = useCallback((voiceId: string) => {
    setPreviewing(voiceId);
    previewVoice(voiceId)
      .catch(() => setFailed("Aperçu de la voix indisponible."))
      .finally(() => setPreviewing(null));
  }, []);

  const refresh = useCallback(async () => {
    try {
      setPiper(await api.getPiperLibrary());
    } catch {
      setFailed("Impossible de charger la bibliothèque de voix.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Interrogation tant qu'un téléchargement est en cours.
  const downloading = piper?.voices.some((v) => v.status === "downloading") ?? false;
  useEffect(() => {
    if (!downloading) {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (pollRef.current === null) {
      pollRef.current = window.setInterval(() => void refresh(), 1200);
    }
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [downloading, refresh]);

  const download = useCallback(async (id: string) => {
    setBusy(true);
    setFailed(null);
    try {
      setPiper(await api.downloadPiperVoice(id));
    } catch {
      setFailed("Le téléchargement n'a pas pu démarrer.");
    } finally {
      setBusy(false);
    }
  }, []);

  const remove = useCallback(async (id: string) => {
    setBusy(true);
    setFailed(null);
    try {
      setPiper(await api.deletePiperVoice(id));
    } catch {
      setFailed("Suppression impossible.");
    } finally {
      setBusy(false);
    }
  }, []);

  return (
    <>
      <h1 className="settings-title">Voix</h1>
      <p className="settings-subtitle">
        Choisis le moteur de synthèse vocale. Vivienne est active par défaut&nbsp;; Piper
        et Orpheus ne sont téléchargés que si tu le souhaites, pour garder Timbre léger.
      </p>

      <div className="voice-engines">
        {/* Vivienne */}
        <section className="voice-engine">
          <div className="voice-engine-head">
            <div>
              <h2 className="voice-engine-name">Vivienne</h2>
              <p className="voice-engine-tagline">La voix par défaut, prête à l'emploi</p>
            </div>
            <div className="voice-engine-head-actions">
              <PreviewButton
                voiceId="fr-FR-VivienneMultilingualNeural"
                previewing={previewing}
                onPreview={preview}
              />
              <span className="voice-engine-state voice-engine-state--active">Active</span>
            </div>
          </div>
          <p className="voice-engine-desc">
            Voix neurale de Microsoft, très naturelle et à faible latence. Multilingue
            (français, anglais, espagnol…). La synthèse se fait sur les serveurs de
            Microsoft — notre seule exception au « tout local » — et sans émotions.
          </p>
          <Badges badges={VIVIENNE_BADGES} />
        </section>

        {/* Piper */}
        <section className="voice-engine">
          <div className="voice-engine-head">
            <div>
              <h2 className="voice-engine-name">Piper</h2>
              <p className="voice-engine-tagline">100 % local, léger, hors-ligne</p>
            </div>
          </div>
          <p className="voice-engine-desc">
            Moteur entièrement local : chaque voix est un petit fichier qui tourne sur le
            processeur, sans carte graphique ni connexion. Télécharge une ou plusieurs
            voix ci-dessous — elles apparaîtront ensuite dans l'éditeur de personas.
          </p>
          <Badges badges={PIPER_BADGES} />

          <div className="piper-voices">
            {piper === null ? (
              <p className="piper-hint">Chargement…</p>
            ) : (
              piper.voices.map((voice) => (
                <PiperVoiceRow
                  key={voice.id}
                  voice={voice}
                  busy={busy}
                  previewing={previewing}
                  onDownload={download}
                  onDelete={remove}
                  onPreview={preview}
                />
              ))
            )}
            {failed !== null && <p className="piper-voice-error">{failed}</p>}
          </div>
        </section>

        {/* Orpheus */}
        <section className="voice-engine voice-engine--soon">
          <div className="voice-engine-head">
            <div>
              <h2 className="voice-engine-name">Orpheus</h2>
              <p className="voice-engine-tagline">Voix expressive avec émotions</p>
            </div>
            <span className="voice-engine-state">Bientôt</span>
          </div>
          <p className="voice-engine-desc">
            Moteur local basé sur un LLM : il gère les émotions (rires, soupirs…) avec un
            rendu proche de l'humain. Le plus gourmand — une carte NVIDIA sera recommandée.
            Intégration prévue via LM Studio dans une prochaine version.
          </p>
          <Badges badges={ORPHEUS_BADGES} />
        </section>
      </div>
    </>
  );
}

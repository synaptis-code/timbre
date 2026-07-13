import { useCallback, useEffect, useState } from "react";
import { api, type OrpheusStatus } from "../api";

/** Panneau d'activation d'Orpheus (voix expressive) dans la bibliothèque de voix.
 *
 * Orpheus tourne via un modèle GGUF chargé dans LM Studio + un décodeur SNAC
 * (torch, installé à la demande). L'utilisateur saisit le nom du modèle LM Studio. */
export function OrpheusPanel({ onChanged }: { onChanged: () => void }) {
  const [status, setStatus] = useState<OrpheusStatus | null>(null);
  const [model, setModel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const orpheus = await api.getOrpheus();
      setStatus(orpheus);
      setModel((prev) => (prev === "" ? orpheus.model : prev));
    } catch {
      /* silencieux : le panneau reste masqué si l'API échoue */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const enable = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await api.enableOrpheus(model.trim()));
      onChanged();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Activation impossible (voir les logs serveur).",
      );
    } finally {
      setBusy(false);
    }
  }, [model, onChanged]);

  const disable = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await api.disableOrpheus());
      onChanged();
    } catch {
      setError("Désactivation impossible.");
    } finally {
      setBusy(false);
    }
  }, [onChanged]);

  if (status === null) return null;

  return (
    <section className="orpheus-panel">
      <div className="orpheus-head">
        <div>
          <h3 className="orpheus-title">Orpheus · voix expressive</h3>
          <p className="orpheus-tagline">Émotions (rires, soupirs…) — via LM Studio + GPU</p>
        </div>
        {status.enabled ? (
          <span className="voice-engine-state voice-engine-state--active">Activée</span>
        ) : (
          <span className="voice-badge voice-badge--warn">NVIDIA recommandée</span>
        )}
      </div>

      <p className="orpheus-desc">
        Charge un modèle <strong>Orpheus au format GGUF dans LM Studio</strong>, puis indique
        ci-dessous son identifiant. L'activation installe le décodeur audio (torch — plusieurs
        centaines de Mo, une seule fois). Les voix Orpheus apparaîtront ensuite dans l'éditeur
        de personas.
      </p>

      {status.enabled ? (
        <div className="orpheus-actions">
          <span className="piper-voice-ready">✓ Activée · modèle « {status.model} »</span>
          <button type="button" className="piper-link-danger" onClick={disable} disabled={busy}>
            Désactiver
          </button>
        </div>
      ) : (
        <div className="orpheus-form">
          <input
            className="orpheus-input"
            value={model}
            onChange={(event) => setModel(event.target.value)}
            placeholder="Nom du modèle Orpheus dans LM Studio (ex. orpheus-3b-0.1-ft)"
            aria-label="Modèle Orpheus"
          />
          <button
            type="button"
            className="btn-primary btn-compact"
            onClick={enable}
            disabled={busy || model.trim() === ""}
          >
            {busy ? "Installation…" : status.ready ? "Activer" : "Installer et activer"}
          </button>
        </div>
      )}
      {busy && !status.enabled && (
        <p className="orpheus-hint">
          Installation de torch en cours — ça peut prendre plusieurs minutes la première fois.
        </p>
      )}
      {error !== null && <p className="piper-voice-error">{error}</p>}
    </section>
  );
}

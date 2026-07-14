import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type PiperLibrary, type PiperVoiceInfo } from "../api";
import { previewVoice } from "../voicePreview";
import { PreviewButton } from "./PreviewButton";
import { formatMo } from "../format";

interface RowProps {
  voice: PiperVoiceInfo;
  busy: boolean;
  previewing: string | null;
  onDownload: (id: string) => void;
  onDelete: (id: string) => void;
  onPreview: (id: string) => void;
}

function PiperVoiceRow({ voice, busy, previewing, onDownload, onDelete, onPreview }: RowProps) {
  const percent =
    voice.status === "downloading" && voice.size_bytes > 0
      ? Math.min(100, Math.round((voice.received / voice.size_bytes) * 100))
      : 0;

  return (
    <div className="piper-voice">
      <div className="piper-voice-info">
        <span className="piper-voice-name">{voice.label}</span>
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

interface LanguageGroup {
  code: string;
  native: string;
  english: string;
  voices: PiperVoiceInfo[];
}

export function PiperTab({ onChanged }: { onChanged: () => void }) {
  const [piper, setPiper] = useState<PiperLibrary | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const pollRef = useRef<number | null>(null);
  const wasDownloading = useRef(false);

  const preview = useCallback((voiceId: string) => {
    setPreviewing(voiceId);
    previewVoice(voiceId)
      .catch(() => setFailed("Aperçu de la voix indisponible."))
      .finally(() => setPreviewing(null));
  }, []);

  const refresh = useCallback(async () => {
    try {
      setPiper(await api.getPiperLibrary());
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const downloading = piper?.voices.some((v) => v.status === "downloading") ?? false;

  useEffect(() => {
    if (wasDownloading.current && !downloading) onChanged();
    wasDownloading.current = downloading;
  }, [downloading, onChanged]);

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

  const remove = useCallback(
    async (id: string) => {
      setBusy(true);
      setFailed(null);
      try {
        setPiper(await api.deletePiperVoice(id));
        onChanged();
      } catch {
        setFailed("Suppression impossible.");
      } finally {
        setBusy(false);
      }
    },
    [onChanged],
  );

  const installed = useMemo(
    () => (piper?.voices ?? []).filter((v) => v.status === "ready" || v.status === "downloading"),
    [piper],
  );

  const groups = useMemo<LanguageGroup[]>(() => {
    const q = query.trim().toLowerCase();
    const byLang = new Map<string, LanguageGroup>();
    for (const voice of piper?.voices ?? []) {
      const matches =
        q === "" ||
        voice.language_english.toLowerCase().includes(q) ||
        voice.language_native.toLowerCase().includes(q) ||
        voice.language_code.toLowerCase().includes(q) ||
        voice.label.toLowerCase().includes(q);
      if (!matches) continue;
      let group = byLang.get(voice.language_code);
      if (group === undefined) {
        group = {
          code: voice.language_code,
          native: voice.language_native,
          english: voice.language_english,
          voices: [],
        };
        byLang.set(voice.language_code, group);
      }
      group.voices.push(voice);
    }
    return [...byLang.values()].sort(
      (a, b) => b.voices.length - a.voices.length || a.english.localeCompare(b.english),
    );
  }, [piper, query]);

  const rowProps = { busy, previewing, onDownload: download, onDelete: remove, onPreview: preview };

  if (piper === null) {
    return loadFailed ? (
      <div className="piper-load-error">
        <p className="piper-hint">Catalogue de voix indisponible.</p>
        <button type="button" className="btn-secondary btn-compact" onClick={() => void refresh()}>
          Réessayer
        </button>
      </div>
    ) : (
      <p className="piper-hint">Chargement du catalogue…</p>
    );
  }

  return (
    <div className="piper-tab">
      <p className="tab-intro">
        Voix locales Piper — une cinquantaine de langues, 100 % hors-ligne. Chaque voix se
        télécharge séparément.
      </p>
      <input
        className="piper-search"
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Chercher une langue (français, english, español, deutsch…)"
        aria-label="Chercher une langue"
      />

      {installed.length > 0 && query.trim() === "" && (
        <div className="piper-installed">
          <p className="piper-group-label">Vos voix</p>
          {installed.map((voice) => (
            <PiperVoiceRow key={voice.id} voice={voice} {...rowProps} />
          ))}
        </div>
      )}

      <div className="piper-langs">
        {groups.length === 0 ? (
          <p className="piper-hint">Aucune langue ne correspond à « {query} ».</p>
        ) : (
          groups.map((group) => (
            <details key={group.code} className="piper-lang" open={query.trim() !== ""}>
              <summary className="piper-lang-summary">
                <span className="piper-lang-name">{group.native}</span>
                <span className="piper-lang-count">{group.voices.length}</span>
              </summary>
              <div className="piper-lang-voices">
                {group.voices.map((voice) => (
                  <PiperVoiceRow key={voice.id} voice={voice} {...rowProps} />
                ))}
              </div>
            </details>
          ))
        )}
      </div>
      {failed !== null && <p className="piper-voice-error">{failed}</p>}
    </div>
  );
}

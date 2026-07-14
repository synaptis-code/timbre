import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type KokoroLibrary, type KokoroVoiceInfo } from "../api";
import { previewVoice } from "../voicePreview";
import { PreviewButton } from "./PreviewButton";
import { formatMo } from "../format";

interface LanguageGroup {
  key: string;
  native: string;
  voices: KokoroVoiceInfo[];
}

export function KokoroTab({ onChanged }: { onChanged: () => void }) {
  const [lib, setLib] = useState<KokoroLibrary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const pollRef = useRef<number | null>(null);

  const preview = useCallback((voiceId: string) => {
    setPreviewing(voiceId);
    previewVoice(voiceId)
      .catch(() => setError("Aperçu de la voix indisponible."))
      .finally(() => setPreviewing(null));
  }, []);

  const refresh = useCallback(async () => {
    try {
      setLib(await api.getKokoro());
    } catch {
      setError("Impossible de charger l'état de Kokoro.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const downloading = lib?.status === "downloading";
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

  // Quand l'installation se termine, rafraîchir les voix du persona.
  const wasDownloading = useRef(false);
  useEffect(() => {
    if (wasDownloading.current && !downloading) onChanged();
    wasDownloading.current = downloading ?? false;
  }, [downloading, onChanged]);

  const install = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setLib(await api.installKokoro());
    } catch {
      setError("L'installation n'a pas pu démarrer.");
    } finally {
      setBusy(false);
    }
  }, []);

  const uninstall = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setLib(await api.uninstallKokoro());
      onChanged();
    } catch {
      setError("Désinstallation impossible.");
    } finally {
      setBusy(false);
    }
  }, [onChanged]);

  const groups = useMemo<LanguageGroup[]>(() => {
    const q = query.trim().toLowerCase();
    const byLang = new Map<string, LanguageGroup>();
    for (const voice of lib?.voices ?? []) {
      const matches =
        q === "" ||
        voice.language_english.toLowerCase().includes(q) ||
        voice.language_native.toLowerCase().includes(q) ||
        voice.label.toLowerCase().includes(q);
      if (!matches) continue;
      let group = byLang.get(voice.language_native);
      if (group === undefined) {
        group = { key: voice.language_native, native: voice.language_native, voices: [] };
        byLang.set(voice.language_native, group);
      }
      group.voices.push(voice);
    }
    return [...byLang.values()].sort((a, b) => b.voices.length - a.voices.length);
  }, [lib, query]);

  if (lib === null) return <p className="piper-hint">Chargement…</p>;

  const percent =
    lib.status === "downloading" && lib.total > 0
      ? Math.min(100, Math.round((lib.received / lib.total) * 100))
      : 0;

  return (
    <div className="kokoro-tab">
      <p className="tab-intro">
        Voix locales Kokoro — très naturelles, légères (tournent sur le processeur),
        multilingues. Un seul téléchargement (~350 Mo) débloque les {lib.voices.length} voix.
      </p>

      {lib.status !== "ready" ? (
        <div className="kokoro-install">
          {lib.status === "downloading" ? (
            <div className="piper-progress">
              <div className="piper-progress-track">
                <div className="piper-progress-fill" style={{ width: `${percent}%` }} />
              </div>
              <span className="piper-progress-label">{percent}%</span>
            </div>
          ) : (
            <button
              type="button"
              className="btn-primary btn-compact"
              onClick={install}
              disabled={busy}
            >
              {busy ? "Installation…" : `Installer Kokoro (~${formatMo(lib.total)})`}
            </button>
          )}
          {lib.status === "error" && (
            <p className="piper-voice-error">{lib.error ?? "Échec du téléchargement."}</p>
          )}
        </div>
      ) : (
        <>
          <div className="kokoro-installed-head">
            <span className="piper-voice-ready">✓ Kokoro installé</span>
            <button
              type="button"
              className="piper-link-danger"
              onClick={uninstall}
              disabled={busy}
            >
              Désinstaller
            </button>
          </div>

          <input
            className="piper-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Chercher une langue ou une voix…"
            aria-label="Chercher une voix Kokoro"
          />

          <div className="piper-langs">
            {groups.length === 0 ? (
              <p className="piper-hint">Aucune voix ne correspond.</p>
            ) : (
              groups.map((group) => (
                <details key={group.key} className="piper-lang" open={query.trim() !== ""}>
                  <summary className="piper-lang-summary">
                    <span className="piper-lang-name">{group.native}</span>
                    <span className="piper-lang-count">{group.voices.length}</span>
                  </summary>
                  <div className="piper-lang-voices">
                    {group.voices.map((voice) => (
                      <div key={voice.id} className="piper-voice">
                        <div className="piper-voice-info">
                          <span className="piper-voice-name">{voice.label}</span>
                        </div>
                        <PreviewButton
                          voiceId={voice.id}
                          previewing={previewing}
                          onPreview={preview}
                        />
                      </div>
                    ))}
                  </div>
                </details>
              ))
            )}
          </div>
        </>
      )}
      {error !== null && <p className="piper-voice-error">{error}</p>}
    </div>
  );
}

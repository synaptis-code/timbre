import { useEffect, useMemo, useRef, useState } from "react";
import { api, type ProviderInfo, type ProvidersState } from "../api";
import { ProviderLogo } from "../providerLogos";
import { ChevronDownIcon } from "../icons";


/** Réglages → Fournisseur d'IA (façon AnythingLLM) : un sélecteur avec liste
 * recherchable + logos, puis un formulaire dont les champs dépendent du
 * fournisseur. Les modèles se chargent automatiquement — aucun bouton. */
export function ProvidersSection() {
  const [state, setState] = useState<ProvidersState | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [search, setSearch] = useState("");

  // Brouillon de configuration du fournisseur sélectionné.
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [advanced, setAdvanced] = useState(false);

  const [models, setModels] = useState<string[]>([]);
  const [modelsState, setModelsState] = useState<"idle" | "loading" | "error">("idle");
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const selected: ProviderInfo | null = state?.providers.find((p) => p.id === selectedId) ?? null;

  useEffect(() => {
    void api
      .getProviders()
      .then((loaded) => {
        setState(loaded);
        setSelectedId((prev) => prev ?? loaded.active);
      })
      .catch((error: unknown) => setFeedback({ kind: "error", text: String(error) }));
  }, []);

  // Recharge le brouillon quand on change de fournisseur.
  useEffect(() => {
    if (selected === null) return;
    setBaseUrl(selected.base_url);
    setModel(selected.model ?? "");
    setApiKey("");
    setAdvanced(false);
    setFeedback(null);
    setModels([]);
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-détection des modèles : dès qu'on peut (local, ou clé saisie/enregistrée).
  const canList =
    selected !== null && (!selected.needs_key || selected.has_key || apiKey.trim() !== "");
  useEffect(() => {
    if (selected === null || !canList) {
      setModels([]);
      setModelsState("idle");
      return;
    }
    let cancelled = false;
    setModelsState("loading");
    const handle = window.setTimeout(() => {
      void api
        .listProviderModels(selected.id, {
          ...(apiKey.trim() !== "" ? { api_key: apiKey.trim() } : {}),
          ...(baseUrl.trim() !== "" ? { base_url: baseUrl.trim() } : {}),
        })
        .then((result) => {
          if (cancelled) return;
          setModels(result.models);
          setModelsState("idle");
          setModel((current) => {
            if (current !== "" && result.models.includes(current)) return current;
            if (selected.id === "lmstudio") return current; // "" = automatique
            return result.models[0] ?? current;
          });
        })
        .catch(() => {
          if (!cancelled) setModelsState("error");
        });
    }, 500);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [selectedId, apiKey, baseUrl, canList]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty =
    selected !== null &&
    (selectedId !== state?.active ||
      baseUrl !== selected.base_url ||
      model !== (selected.model ?? "") ||
      apiKey.trim() !== "");

  const save = () => {
    if (selected === null) return;
    setSaving(true);
    setFeedback(null);
    void (async () => {
      try {
        await api.updateProvider(selected.id, {
          base_url: baseUrl.trim(),
          model: model.trim(),
          ...(apiKey.trim() !== "" ? { api_key: apiKey.trim() } : {}),
        });
        const next = await api.setActiveProvider(selected.id);
        setState(next);
        setApiKey("");
      } catch (error) {
        setFeedback({
          kind: "error",
          text: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setSaving(false);
      }
    })();
  };

  if (state === null || selected === null) {
    return (
      <>
        <h1 className="settings-title">Fournisseur d'IA</h1>
        <p className="settings-subtitle">{feedback?.text ?? "Chargement…"}</p>
      </>
    );
  }

  return (
    <>
      <div className="settings-head-row">
        <div>
          <h1 className="settings-title">Fournisseur d'IA</h1>
          <p className="settings-subtitle">
            Timbre est local d'abord. Un fournisseur cloud est possible — sa clé reste sur cette
            machine, mais tes conversations partiront chez lui.
          </p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={save}
          disabled={!dirty || saving}
          title={dirty ? "Enregistrer et activer" : "Aucun changement"}
        >
          Enregistrer
        </button>
      </div>

      <p className="provider-field-label">Fournisseur LLM</p>
      <ProviderPicker
        state={state}
        selected={selected}
        open={pickerOpen}
        search={search}
        onToggle={() => setPickerOpen((o) => !o)}
        onSearch={setSearch}
        onPick={(id) => {
          setSelectedId(id);
          setPickerOpen(false);
          setSearch("");
        }}
      />

      <div className="provider-form">
        {selected.needs_key && (
          <label className="provider-field">
            <span>Clé API {selected.has_key && <em>· une clé est enregistrée</em>}</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={selected.has_key ? "••••••••  (laisser vide pour conserver)" : "Clé API"}
              autoComplete="off"
            />
          </label>
        )}

        <label className="provider-field">
          <span>
            Modèle{" "}
            {modelsState === "loading" && <em>· recherche…</em>}
            {modelsState === "error" && <em className="provider-warn">· indisponible</em>}
          </span>
          {models.length > 0 ? (
            <select value={model} onChange={(event) => setModel(event.target.value)}>
              {selected.id === "lmstudio" && <option value="">Automatique (modèle chargé)</option>}
              {models.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder={
                selected.needs_key && !canList
                  ? "Renseigne la clé pour lister les modèles"
                  : selected.id === "lmstudio"
                    ? "Automatique — laisse vide"
                    : "nom du modèle"
              }
              spellCheck={false}
            />
          )}
        </label>

        <button
          type="button"
          className="provider-advanced-toggle"
          onClick={() => setAdvanced((a) => !a)}
        >
          {advanced ? "Masquer" : "Afficher"} les paramètres avancés {advanced ? "▴" : "▾"}
        </button>

        {advanced && (
          <label className="provider-field">
            <span>URL de base</span>
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              spellCheck={false}
            />
          </label>
        )}

        {feedback !== null && (
          <p className={`provider-feedback provider-feedback--${feedback.kind}`}>{feedback.text}</p>
        )}
      </div>
    </>
  );
}

// ── Sélecteur de fournisseur (carte + liste recherchable) ──────────────────

interface PickerProps {
  state: ProvidersState;
  selected: ProviderInfo;
  open: boolean;
  search: string;
  onToggle: () => void;
  onSearch: (value: string) => void;
  onPick: (id: string) => void;
}

function ProviderPicker({ state, selected, open, search, onToggle, onSearch, onPick }: PickerProps) {
  const ref = useRef<HTMLDivElement>(null);
  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    return state.providers.filter(
      (p) => q === "" || p.name.toLowerCase().includes(q) || p.description.toLowerCase().includes(q),
    );
  }, [state.providers, search]);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (ref.current !== null && !ref.current.contains(event.target as Node)) onToggle();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open, onToggle]);

  return (
    <div className="provider-picker" ref={ref}>
      <button type="button" className="provider-card-btn" onClick={onToggle} aria-expanded={open}>
        <ProviderLogo id={selected.id} />
        <span className="provider-card-text">
          <strong>
            {selected.name}
            {selected.id === state.active && (
              <span className="provider-tag" style={{ marginLeft: "8px" }}>
                actif
              </span>
            )}
          </strong>
          <span>{selected.description}</span>
        </span>
        <span className="provider-card-chevron" aria-hidden="true">
          <ChevronDownIcon size={14} />
        </span>
      </button>

      {open && (
        <div className="provider-menu">
          <div className="provider-menu-search">
            <input
              autoFocus
              value={search}
              onChange={(event) => onSearch(event.target.value)}
              placeholder="Rechercher un fournisseur…"
              aria-label="Rechercher un fournisseur"
            />
          </div>
          <ul className="provider-menu-list" role="listbox">
            {matches.map((provider) => (
              <li key={provider.id}>
                <button
                  type="button"
                  className={`provider-menu-item ${
                    provider.id === selected.id ? "provider-menu-item--on" : ""
                  }`}
                  onClick={() => onPick(provider.id)}
                >
                  <ProviderLogo id={provider.id} size={30} />
                  <span className="provider-card-text">
                    <strong>
                      {provider.name}
                      {provider.id === state.active && <span className="provider-tag">actif</span>}
                    </strong>
                    <span>{provider.description}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

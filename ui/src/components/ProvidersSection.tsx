import { useEffect, useState } from "react";
import { api, type ProviderInfo, type ProvidersState } from "../api";

/** Section Réglages → Fournisseur d'IA : choix, configuration (clé, URL,
 * modèle) et activation. Les clés restent en base locale, jamais affichées. */
export function ProvidersSection() {
  const [state, setState] = useState<ProvidersState | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const selected: ProviderInfo | null =
    state?.providers.find((p) => p.id === selectedId) ?? null;

  useEffect(() => {
    void api
      .getProviders()
      .then((loaded) => {
        setState(loaded);
        setSelectedId((prev) => prev ?? loaded.active);
      })
      .catch((error: unknown) => setFeedback({ kind: "error", text: String(error) }));
  }, []);

  // Recharge le formulaire quand on change de fournisseur sélectionné.
  useEffect(() => {
    if (selected === null) return;
    setBaseUrl(selected.base_url);
    setModel(selected.model ?? "");
    setApiKey("");
    setModels([]);
    setFeedback(null);
  }, [selectedId, selected === null]); // eslint-disable-line react-hooks/exhaustive-deps

  if (state === null) {
    return (
      <section className="color-block color-block--lilac">
        <p className="eyebrow">Fournisseur d'IA</p>
        <p className="color-block-body">{feedback?.text ?? "Chargement…"}</p>
      </section>
    );
  }

  const run = (action: () => Promise<ProvidersState | void>, okText: string) => {
    setBusy(true);
    setFeedback(null);
    void action()
      .then((next) => {
        if (next) setState(next);
        setFeedback({ kind: "ok", text: okText });
        setApiKey("");
      })
      .catch((error: unknown) =>
        setFeedback({ kind: "error", text: error instanceof Error ? error.message : String(error) }),
      )
      .finally(() => setBusy(false));
  };

  const save = () =>
    run(
      () =>
        api.updateProvider(selected!.id, {
          base_url: baseUrl.trim(),
          model: model.trim(),
          ...(apiKey.trim() !== "" ? { api_key: apiKey.trim() } : {}),
        }),
      "Configuration enregistrée.",
    );

  const activate = () =>
    run(async () => {
      await api.updateProvider(selected!.id, {
        base_url: baseUrl.trim(),
        model: model.trim(),
        ...(apiKey.trim() !== "" ? { api_key: apiKey.trim() } : {}),
      });
      return api.setActiveProvider(selected!.id);
    }, `${selected!.name} est maintenant le fournisseur actif.`);

  const loadModels = () =>
    run(async () => {
      await api.updateProvider(selected!.id, {
        base_url: baseUrl.trim(),
        ...(apiKey.trim() !== "" ? { api_key: apiKey.trim() } : {}),
      });
      const result = await api.listProviderModels(selected!.id);
      setModels(result.models);
      if (result.models.length > 0 && model === "") setModel(result.models[0]);
    }, "Modèles chargés.");

  return (
    <section className="color-block color-block--lilac">
      <p className="eyebrow">Fournisseur d'IA</p>
      <h2 className="color-block-title">Fournisseur d'IA</h2>
      <p className="color-block-body">
        Timbre est local d'abord. Les fournisseurs cloud sont possibles — leurs clés restent
        stockées sur cette machine, mais tes conversations partiront chez eux.
      </p>

      <div className="provider-chips">
        {state.providers.map((provider) => (
          <button
            key={provider.id}
            type="button"
            className={`chip chip--btn ${
              provider.id === state.active
                ? "chip--active"
                : provider.id === selectedId
                  ? "chip--selected"
                  : ""
            }`}
            onClick={() => setSelectedId(provider.id)}
            title={provider.id === state.active ? "Fournisseur actif" : provider.name}
          >
            {provider.name}
          </button>
        ))}
      </div>

      {selected !== null && (
        <div className="provider-form">
          <div className="provider-form-head">
            <strong>{selected.name}</strong>
            {selected.id === state.active && <span className="chip chip--active">Actif</span>}
            {!selected.local && (
              <span className="provider-cloud-warn">
                Cloud — tes conversations seront envoyées à {selected.name}.
              </span>
            )}
          </div>

          {selected.id === "lmstudio" ? (
            <p className="settings-hint">
              Détection automatique du modèle chargé dans LM Studio — rien à configurer.
            </p>
          ) : (
            <>
              <label className="provider-field">
                <span>URL de base</span>
                <input
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  spellCheck={false}
                />
              </label>
              {selected.needs_key && (
                <label className="provider-field">
                  <span>Clé API {selected.has_key && "· une clé est enregistrée"}</span>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder={selected.has_key ? "••••••••  (laisser vide pour conserver)" : ""}
                    autoComplete="off"
                  />
                </label>
              )}
              <label className="provider-field">
                <span>Modèle</span>
                <div className="provider-model-row">
                  <input
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    list={`models-${selected.id}`}
                    spellCheck={false}
                  />
                  <datalist id={`models-${selected.id}`}>
                    {models.map((name) => (
                      <option key={name} value={name} />
                    ))}
                  </datalist>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={loadModels}
                    disabled={busy}
                  >
                    Charger les modèles
                  </button>
                </div>
              </label>
            </>
          )}

          <div className="provider-actions">
            {selected.id !== "lmstudio" && (
              <button type="button" className="btn-secondary" onClick={save} disabled={busy}>
                Enregistrer
              </button>
            )}
            <button
              type="button"
              className="btn-primary"
              onClick={activate}
              disabled={busy || selected.id === state.active}
            >
              Utiliser ce fournisseur
            </button>
          </div>

          {feedback !== null && (
            <p className={`provider-feedback provider-feedback--${feedback.kind}`}>
              {feedback.text}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

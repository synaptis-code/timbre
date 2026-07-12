"""Registre des fournisseurs d'IA et gestionnaire de backend actif.

La configuration (fournisseur actif, clés API, modèles) vit dans la base
SQLite locale — les clés ne quittent jamais la machine. Le backend LLM est
permutable à chaud : le changement prend effet au tour suivant.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from timbre.config import Settings
from timbre.plugins.base import LLMBackend, LLMError
from timbre.plugins.llm.anthropic import AnthropicBackend, fetch_anthropic_models
from timbre.plugins.llm.lmstudio import LMStudioBackend, fetch_lmstudio_models
from timbre.plugins.llm.openai_compat import OpenAICompatibleBackend, fetch_openai_models
from timbre.storage import Storage

logger = logging.getLogger(__name__)

Kind = Literal["lmstudio", "openai", "anthropic"]


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    kind: Kind
    default_base_url: str
    needs_key: bool
    local: bool
    description: str


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        "lmstudio",
        "LM Studio",
        "lmstudio",
        "http://127.0.0.1:1234",
        False,
        True,
        "Découvre, télécharge et lance des LLM locaux en quelques clics.",
    ),
    ProviderSpec(
        "ollama",
        "Ollama",
        "openai",
        "http://127.0.0.1:11434/v1",
        False,
        True,
        "Lance des modèles locaux (Llama, Mistral…) sur ta machine.",
    ),
    ProviderSpec(
        "localai",
        "LocalAI",
        "openai",
        "http://127.0.0.1:8080/v1",
        False,
        True,
        "Serveur d'inférence local compatible OpenAI.",
    ),
    ProviderSpec(
        "lemonade",
        "Lemonade",
        "openai",
        "http://127.0.0.1:8000/api/v1",
        False,
        True,
        "Serveur local accéléré (AMD Ryzen AI / GPU).",
    ),
    ProviderSpec(
        "openai",
        "OpenAI",
        "openai",
        "https://api.openai.com/v1",
        True,
        False,
        "GPT-4o, GPT-4.1 et compagnie — le choix standard.",
    ),
    ProviderSpec(
        "anthropic",
        "Anthropic",
        "anthropic",
        "https://api.anthropic.com",
        True,
        False,
        "Claude, un assistant IA sûr et de qualité.",
    ),
    ProviderSpec(
        "gemini",
        "Google Gemini",
        "openai",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        True,
        False,
        "Les modèles Gemini de Google.",
    ),
    ProviderSpec(
        "nim",
        "NVIDIA NIM",
        "openai",
        "https://integrate.api.nvidia.com/v1",
        True,
        False,
        "Microservices d'inférence NVIDIA.",
    ),
    ProviderSpec(
        "together",
        "Together AI",
        "openai",
        "https://api.together.xyz/v1",
        True,
        False,
        "Modèles open source hébergés, rapides.",
    ),
    ProviderSpec(
        "deepseek",
        "DeepSeek",
        "openai",
        "https://api.deepseek.com/v1",
        True,
        False,
        "Les modèles DeepSeek (chat et raisonnement).",
    ),
    ProviderSpec(
        "groq",
        "Groq",
        "openai",
        "https://api.groq.com/openai/v1",
        True,
        False,
        "Inférence ultra-rapide sur LPU.",
    ),
    ProviderSpec(
        "mistral",
        "Mistral",
        "openai",
        "https://api.mistral.ai/v1",
        True,
        False,
        "Les modèles de Mistral AI.",
    ),
    ProviderSpec(
        "openrouter",
        "OpenRouter",
        "openai",
        "https://openrouter.ai/api/v1",
        True,
        False,
        "Un seul point d'accès vers des centaines de modèles.",
    ),
    ProviderSpec(
        "xai",
        "xAI",
        "openai",
        "https://api.x.ai/v1",
        True,
        False,
        "Les modèles Grok de xAI.",
    ),
    ProviderSpec(
        "perplexity",
        "Perplexity",
        "openai",
        "https://api.perplexity.ai",
        True,
        False,
        "Modèles Sonar connectés au web.",
    ),
    ProviderSpec(
        "fireworks",
        "Fireworks AI",
        "openai",
        "https://api.fireworks.ai/inference/v1",
        True,
        False,
        "Inférence rapide pour modèles open source.",
    ),
    ProviderSpec(
        "sambanova",
        "SambaNova",
        "openai",
        "https://api.sambanova.ai/v1",
        True,
        False,
        "Inférence très rapide sur puces dédiées.",
    ),
    ProviderSpec(
        "cohere",
        "Cohere",
        "openai",
        "https://api.cohere.ai/compatibility/v1",
        True,
        False,
        "Les modèles Command de Cohere.",
    ),
)

SPECS_BY_ID: dict[str, ProviderSpec] = {spec.id: spec for spec in PROVIDERS}

ACTIVE_KEY = "llm.active"


def config_key(provider_id: str, field: str) -> str:
    return f"llm.{provider_id}.{field}"


class ProviderManager:
    """Détient le backend LLM courant, reconstruit depuis la config locale."""

    def __init__(
        self, storage: Storage, settings: Settings, override: LLMBackend | None = None
    ) -> None:
        self._storage = storage
        self._settings = settings
        self._override = override
        self._current: LLMBackend | None = None
        self._active_id = "lmstudio"

    @property
    def active_id(self) -> str:
        return self._active_id

    @property
    def current(self) -> LLMBackend:
        if self._override is not None:
            return self._override
        if self._current is None:
            self._current = self._build_lmstudio(self._settings.lmstudio_base_url)
        return self._current

    async def reload(self) -> None:
        """Relit la config locale et permute le backend (effet au tour suivant)."""
        if self._override is not None:
            return
        active_id = await self._storage.get_setting(ACTIVE_KEY, "lmstudio")
        spec = SPECS_BY_ID.get(active_id)
        if spec is None:
            logger.warning("fournisseur inconnu « %s » — retour à LM Studio", active_id)
            spec = SPECS_BY_ID["lmstudio"]
        previous = self._current
        self._current = await self._build(spec)
        self._active_id = spec.id
        logger.info("fournisseur d'IA actif : %s", spec.name)
        if previous is not None:
            await previous.aclose()

    async def aclose(self) -> None:
        if self._current is not None:
            await self._current.aclose()
        if self._override is not None:
            await self._override.aclose()

    async def config(self, spec: ProviderSpec) -> tuple[str, str | None, str | None]:
        """(base_url, api_key, model) configurés pour un fournisseur."""
        default_base = (
            self._settings.lmstudio_base_url if spec.id == "lmstudio" else spec.default_base_url
        )
        stored_base = await self._storage.get_setting(config_key(spec.id, "base_url"), "")
        base_url = stored_base or default_base
        api_key = await self._storage.get_setting(config_key(spec.id, "api_key"), "") or None
        model = await self._storage.get_setting(config_key(spec.id, "model"), "") or None
        return base_url, api_key, model

    async def list_models(
        self,
        provider_id: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> list[str]:
        """Liste les modèles. `api_key`/`base_url` fournis priment sur la config
        stockée — permet de tester une clé fraîchement saisie sans la persister."""
        spec = SPECS_BY_ID.get(provider_id)
        if spec is None:
            raise LLMError("provider_unknown", f"Fournisseur inconnu : {provider_id}")
        stored_base, stored_key, _model = await self.config(spec)
        base = base_url or stored_base
        key = api_key or stored_key
        if spec.kind == "anthropic":
            return await fetch_anthropic_models(base, key or "")
        if spec.kind == "lmstudio":
            return await fetch_lmstudio_models(base)
        return await fetch_openai_models(base, key)

    async def _build(self, spec: ProviderSpec) -> LLMBackend:
        base_url, api_key, model = await self.config(spec)
        if spec.kind == "lmstudio":
            return self._build_lmstudio(base_url, model)
        if spec.kind == "anthropic":
            return AnthropicBackend(
                base_url,
                api_key=api_key or "",
                model=model,
                temperature=self._settings.llm_temperature,
            )
        return OpenAICompatibleBackend(
            base_url,
            provider_name=spec.name,
            api_key=api_key,
            model=model,
            temperature=self._settings.llm_temperature,
        )

    def _build_lmstudio(self, base_url: str, model: str | None = None) -> LMStudioBackend:
        # `model=None` (aucun modèle choisi) → auto-détection du modèle chargé.
        return LMStudioBackend(
            base_url,
            model_override=model or self._settings.llm_model,
            temperature=self._settings.llm_temperature,
        )

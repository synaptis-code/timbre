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
from timbre.plugins.llm.lmstudio import LMStudioBackend
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


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec("lmstudio", "LM Studio", "lmstudio", "http://127.0.0.1:1234", False, True),
    ProviderSpec("ollama", "Ollama", "openai", "http://127.0.0.1:11434/v1", False, True),
    ProviderSpec("localai", "LocalAI", "openai", "http://127.0.0.1:8080/v1", False, True),
    ProviderSpec("lemonade", "Lemonade", "openai", "http://127.0.0.1:8000/api/v1", False, True),
    ProviderSpec("openai", "OpenAI", "openai", "https://api.openai.com/v1", True, False),
    ProviderSpec("anthropic", "Anthropic", "anthropic", "https://api.anthropic.com", True, False),
    ProviderSpec(
        "gemini",
        "Google Gemini",
        "openai",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        True,
        False,
    ),
    ProviderSpec("nim", "NVIDIA NIM", "openai", "https://integrate.api.nvidia.com/v1", True, False),
    ProviderSpec("together", "Together AI", "openai", "https://api.together.xyz/v1", True, False),
    ProviderSpec("deepseek", "DeepSeek", "openai", "https://api.deepseek.com/v1", True, False),
    ProviderSpec("groq", "Groq", "openai", "https://api.groq.com/openai/v1", True, False),
    ProviderSpec("mistral", "Mistral", "openai", "https://api.mistral.ai/v1", True, False),
    ProviderSpec("openrouter", "OpenRouter", "openai", "https://openrouter.ai/api/v1", True, False),
    ProviderSpec("xai", "xAI", "openai", "https://api.x.ai/v1", True, False),
    ProviderSpec("perplexity", "Perplexity", "openai", "https://api.perplexity.ai", True, False),
    ProviderSpec(
        "fireworks", "Fireworks AI", "openai", "https://api.fireworks.ai/inference/v1", True, False
    ),
    ProviderSpec("sambanova", "SambaNova", "openai", "https://api.sambanova.ai/v1", True, False),
    ProviderSpec(
        "cohere", "Cohere", "openai", "https://api.cohere.ai/compatibility/v1", True, False
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

    async def list_models(self, provider_id: str) -> list[str]:
        spec = SPECS_BY_ID.get(provider_id)
        if spec is None:
            raise LLMError("provider_unknown", f"Fournisseur inconnu : {provider_id}")
        base_url, api_key, _model = await self.config(spec)
        if spec.kind == "anthropic":
            return await fetch_anthropic_models(base_url, api_key or "")
        if spec.kind == "lmstudio":
            return await fetch_openai_models(f"{base_url.rstrip('/')}/v1", api_key)
        return await fetch_openai_models(base_url, api_key)

    async def _build(self, spec: ProviderSpec) -> LLMBackend:
        base_url, api_key, model = await self.config(spec)
        if spec.kind == "lmstudio":
            return self._build_lmstudio(base_url)
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

    def _build_lmstudio(self, base_url: str) -> LMStudioBackend:
        return LMStudioBackend(
            base_url,
            model_override=self._settings.llm_model,
            temperature=self._settings.llm_temperature,
        )

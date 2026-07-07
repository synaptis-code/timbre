"""Messages WebSocket typés et validés (union discriminée sur `type`).

Tout message entrant est validé ; un message invalide produit une `ProtocolError`
transformée en message `error` explicite côté client — jamais de plantage silencieux.
Le miroir TypeScript vit dans `ui/src/protocol.ts`, verrouillé par le snapshot
`schemas/ws-protocol.schema.json` (voir tests/unit/test_schema_snapshot.py).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from timbre.protocol.states import AppState


class UserMessage(BaseModel):
    """Client → serveur : texte saisi (ou transcrit, à partir de la Phase 4)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["user_message"] = "user_message"
    text: str = Field(min_length=1)


# Deviendra une union discriminée quand d'autres messages client arriveront
# (interrupt, partage d'écran, …).
ClientMessage = UserMessage


class AiChunk(BaseModel):
    """Serveur → client : fragment de réponse en streaming. `last=True` clôt le tour."""

    type: Literal["ai_chunk"] = "ai_chunk"
    text: str
    last: bool = False


class StateChange(BaseModel):
    """Serveur → client : nouvel état de l'assistant."""

    type: Literal["state_change"] = "state_change"
    state: AppState


class ErrorMessage(BaseModel):
    """Serveur → client : erreur toujours visible, jamais avalée."""

    type: Literal["error"] = "error"
    code: str
    message: str


class ModelInfo(BaseModel):
    """Serveur → client : modèle LLM actif (détecté automatiquement dans LM Studio)."""

    type: Literal["model_info"] = "model_info"
    model: str


class AiAudio(BaseModel):
    """Serveur → client : audio d'une phrase de la réponse, à jouer dans l'ordre reçu.

    `text` est la phrase nettoyée réellement synthétisée (debug/sous-titres).
    """

    type: Literal["ai_audio"] = "ai_audio"
    audio_b64: str
    format: Literal["mp3"] = "mp3"
    text: str


# Union nue pour typer les paramètres ; version annotée pour la (dé)sérialisation.
AnyServerMessage = AiChunk | StateChange | ErrorMessage | ModelInfo | AiAudio
ServerMessage = Annotated[AnyServerMessage, Field(discriminator="type")]

client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
server_message_adapter: TypeAdapter[ServerMessage] = TypeAdapter(ServerMessage)


class ProtocolError(Exception):
    """Message client illisible ou invalide."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_client_message(raw: str | bytes) -> ClientMessage:
    try:
        return client_message_adapter.validate_json(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc']) or '<racine>'}: {err['msg']}"
            for err in exc.errors()
        )
        raise ProtocolError("invalid_message", details) from exc

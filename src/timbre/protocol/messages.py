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
    """Client → serveur : texte saisi au clavier."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["user_message"] = "user_message"
    text: str = Field(min_length=1)


class UserAudio(BaseModel):
    """Client → serveur : une prise de parole détectée par le VAD (WAV 16 kHz mono)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["user_audio"] = "user_audio"
    audio_b64: str = Field(min_length=1)
    format: Literal["wav"] = "wav"


class Interrupt(BaseModel):
    """Client → serveur : stoppe le tour en cours (bouton Stop ou nouvelle prise de parole)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["interrupt"] = "interrupt"


class SetPersona(BaseModel):
    """Client → serveur : change de persona. Refusé avec raison si invalide (jamais en silence)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["set_persona"] = "set_persona"
    persona_id: str = Field(min_length=1)


class ListPersonas(BaseModel):
    """Client → serveur : redemande la liste (re-scan du dossier → rechargement à chaud)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["list_personas"] = "list_personas"


ClientMessage = Annotated[
    UserMessage | UserAudio | Interrupt | SetPersona | ListPersonas,
    Field(discriminator="type"),
]


class AiChunk(BaseModel):
    """Serveur → client : fragment de réponse en streaming. `last=True` clôt le tour.

    `interrupted=True` sur le fragment de clôture : le tour a été coupé, le texte
    affiché est exactement ce qui a été généré (et archivé) avant l'interruption.
    """

    type: Literal["ai_chunk"] = "ai_chunk"
    text: str
    last: bool = False
    interrupted: bool = False


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


class UserTranscript(BaseModel):
    """Serveur → client : ce que l'ASR a compris (affiché comme bulle utilisateur)."""

    type: Literal["user_transcript"] = "user_transcript"
    text: str


class AiAudio(BaseModel):
    """Serveur → client : audio d'une phrase de la réponse, à jouer dans l'ordre reçu.

    `text` est la phrase nettoyée réellement synthétisée (debug/sous-titres).
    """

    type: Literal["ai_audio"] = "ai_audio"
    audio_b64: str
    format: Literal["mp3"] = "mp3"
    text: str


class PersonaSummary(BaseModel):
    """Un persona tel que vu par l'UI : valide (sélectionnable) ou invalide + raison."""

    id: str
    name: str
    valid: bool
    error: str | None = None


class PersonaList(BaseModel):
    """Serveur → client : personas disponibles (statuts inclus) et persona actif."""

    type: Literal["persona_list"] = "persona_list"
    personas: list[PersonaSummary]
    active: str


# Union nue pour typer les paramètres ; version annotée pour la (dé)sérialisation.
AnyServerMessage = (
    AiChunk | StateChange | ErrorMessage | ModelInfo | AiAudio | UserTranscript | PersonaList
)
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

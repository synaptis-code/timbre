"""Endpoint WebSocket : réception validée, erreurs toujours renvoyées au client.

Le tour de conversation tourne dans une tâche annulable : la boucle de
réception reste réactive pendant la génération, ce qui permet `interrupt`
(bouton Stop) et le remplacement d'un tour en cours par une nouvelle prise
de parole — comportement naturel d'une conversation vocale.
"""

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from timbre.config import Settings
from timbre.core.conversation import Conversation
from timbre.core.orchestrator import Orchestrator
from timbre.core.session import Session
from timbre.protocol.messages import (
    AnyServerMessage,
    ErrorMessage,
    Interrupt,
    ListPersonas,
    ProtocolError,
    SetPersona,
    StateChange,
    UserAudio,
    UserMessage,
    parse_client_message,
)
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    orchestrator: Orchestrator = websocket.app.state.orchestrator
    settings: Settings = websocket.app.state.settings
    send_lock = asyncio.Lock()

    async def send(message: AnyServerMessage) -> None:
        # Tolérant : un tour peut encore émettre pendant une déconnexion.
        if websocket.client_state is not WebSocketState.CONNECTED:
            return
        async with send_lock:
            await websocket.send_text(message.model_dump_json())

    session = Session(
        send=send,
        conversation=Conversation(settings.system_prompt),
        persona=orchestrator.fallback_persona,
    )
    turn_task: asyncio.Task[None] | None = None

    async def cancel_current_turn() -> None:
        nonlocal turn_task
        if turn_task is not None and not turn_task.done():
            turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await turn_task
            # Filet de sécurité : l'état repasse toujours à idle (no-op sinon).
            await session.set_state(AppState.IDLE)
        turn_task = None

    async def run_turn(message: UserMessage | UserAudio | SetPersona) -> None:
        try:
            if isinstance(message, UserMessage):
                await orchestrator.handle_user_message(session, message)
            elif isinstance(message, UserAudio):
                await orchestrator.handle_user_audio(session, message)
            else:
                await orchestrator.handle_set_persona(session, message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("erreur pendant le traitement du message")
            await send(
                ErrorMessage(
                    code="internal_error",
                    message="Erreur interne pendant le traitement — voir les logs serveur.",
                )
            )
            await session.set_state(AppState.IDLE)

    # État initial explicite, puis modèle détecté (ou erreur guidante si LM Studio
    # est éteint / vide), puis persona par défaut et liste des personas : le
    # client sait immédiatement à quoi il parle.
    await session.send(StateChange(state=session.state))
    await orchestrator.announce_model(session)
    await orchestrator.init_persona(session)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = parse_client_message(raw)
            except ProtocolError as exc:
                logger.warning("message client invalide : %s", exc.message)
                await session.send(ErrorMessage(code=exc.code, message=exc.message))
                continue
            if isinstance(message, Interrupt):
                await cancel_current_turn()
                continue
            if isinstance(message, ListPersonas):
                await orchestrator.send_persona_list(session)
                continue
            # Une nouvelle entrée remplace le tour en cours (le texte partiel
            # est archivé tel quel par l'orchestrateur).
            await cancel_current_turn()
            turn_task = asyncio.create_task(run_turn(message))
    except WebSocketDisconnect:
        logger.info("client déconnecté")
    finally:
        if turn_task is not None and not turn_task.done():
            turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await turn_task

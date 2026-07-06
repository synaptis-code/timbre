"""Endpoint WebSocket : réception validée, erreurs toujours renvoyées au client."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from timbre.core.orchestrator import Orchestrator
from timbre.core.session import Session
from timbre.protocol.messages import (
    AiChunk,
    ErrorMessage,
    ProtocolError,
    StateChange,
    parse_client_message,
)
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    async def send(message: AiChunk | StateChange | ErrorMessage) -> None:
        await websocket.send_text(message.model_dump_json())

    session = Session(send=send)
    orchestrator = Orchestrator()

    # État initial explicite : le front n'affiche jamais un état supposé.
    await session.send(StateChange(state=session.state))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = parse_client_message(raw)
            except ProtocolError as exc:
                logger.warning("message client invalide : %s", exc.message)
                await session.send(ErrorMessage(code=exc.code, message=exc.message))
                continue
            try:
                await orchestrator.handle_user_message(session, message)
            except Exception:
                logger.exception("erreur pendant le traitement du message")
                await session.send(
                    ErrorMessage(
                        code="internal_error",
                        message="Erreur interne pendant le traitement — voir les logs serveur.",
                    )
                )
                await session.set_state(AppState.IDLE)
    except WebSocketDisconnect:
        logger.info("client déconnecté")

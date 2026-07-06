"""État d'une connexion cliente et émission des messages sortants."""

import logging
from collections.abc import Awaitable, Callable

from timbre.protocol.messages import AiChunk, ErrorMessage, StateChange
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)

SendFn = Callable[[AiChunk | StateChange | ErrorMessage], Awaitable[None]]


class Session:
    """Une conversation cliente : détient l'état courant et le canal de sortie.

    Tout changement d'état passe par `set_state`, qui notifie systématiquement
    le client — le front n'a jamais à deviner l'état du backend.
    """

    def __init__(self, send: SendFn) -> None:
        self._send = send
        self._state = AppState.IDLE

    @property
    def state(self) -> AppState:
        return self._state

    async def set_state(self, state: AppState) -> None:
        if state is self._state:
            return
        logger.debug("état : %s → %s", self._state, state)
        self._state = state
        await self._send(StateChange(state=state))

    async def send(self, message: AiChunk | StateChange | ErrorMessage) -> None:
        await self._send(message)

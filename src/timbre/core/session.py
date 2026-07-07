"""État d'une connexion cliente et émission des messages sortants."""

import logging
from collections.abc import Awaitable, Callable

from timbre.core.conversation import Conversation
from timbre.protocol.messages import AnyServerMessage, StateChange
from timbre.protocol.states import AppState

logger = logging.getLogger(__name__)

SendFn = Callable[[AnyServerMessage], Awaitable[None]]


class Session:
    """Une conversation cliente : état courant, historique et canal de sortie.

    Tout changement d'état passe par `set_state`, qui notifie systématiquement
    le client — le front n'a jamais à deviner l'état du backend.
    """

    def __init__(self, send: SendFn, conversation: Conversation) -> None:
        self._send = send
        self._state = AppState.IDLE
        self.conversation = conversation

    @property
    def state(self) -> AppState:
        return self._state

    async def set_state(self, state: AppState) -> None:
        if state is self._state:
            return
        logger.debug("état : %s → %s", self._state, state)
        self._state = state
        await self._send(StateChange(state=state))

    async def send(self, message: AnyServerMessage) -> None:
        await self._send(message)

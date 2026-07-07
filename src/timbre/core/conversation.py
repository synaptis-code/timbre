"""Historique de conversation.

Règle by-design (bug n°3 du plan) : on n'archive que le texte **réellement
généré**, de façon atomique, indépendamment de l'état de lecture audio. Un tour
assistant interrompu ou partiel est archivé tel quel (jamais inventé, jamais vide).
"""


class Conversation:
    def __init__(self, system_prompt: str) -> None:
        self._system_prompt = system_prompt
        self._turns: list[dict[str, object]] = []

    def set_system_prompt(self, system_prompt: str) -> None:
        """Changement de persona : effet immédiat, l'historique est conservé."""
        self._system_prompt = system_prompt

    def add_user(self, text: str) -> None:
        self._turns.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        """Archive le texte effectivement émis. Un tour vide n'est pas archivé."""
        if text:
            self._turns.append({"role": "assistant", "content": text})

    def to_messages(self) -> list[dict[str, object]]:
        """Format OpenAI chat, prompt système en tête."""
        return [{"role": "system", "content": self._system_prompt}, *self._turns]

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

    def add_user(self, text: str, image: str | None = None) -> None:
        """`image` : data-URL d'une capture d'écran (format multimodal OpenAI).

        Seule la capture la plus récente est conservée dans l'historique : les
        images des tours précédents sont remplacées par un marqueur texte pour
        ne pas faire exploser le contexte (une image ≈ un millier de tokens).
        """
        if image is None:
            self._turns.append({"role": "user", "content": text})
            return
        self._strip_old_images()
        self._turns.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": image}},
                ],
            }
        )

    def _strip_old_images(self) -> None:
        for turn in self._turns:
            content = turn["content"]
            if isinstance(content, list):
                text = next((str(p["text"]) for p in content if p.get("type") == "text"), "")
                turn["content"] = f"{text} [capture d'écran précédente retirée]"

    def add_assistant(self, text: str) -> None:
        """Archive le texte effectivement émis. Un tour vide n'est pas archivé."""
        if text:
            self._turns.append({"role": "assistant", "content": text})

    def to_messages(self) -> list[dict[str, object]]:
        """Format OpenAI chat, prompt système en tête."""
        return [{"role": "system", "content": self._system_prompt}, *self._turns]

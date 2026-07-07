"""Découpage en phrases d'un flux de tokens, pour le TTS streaming (§14 du plan).

Une phrase est close sur `. ! ? …` suivi d'un blanc, ou sur un saut de ligne.
Les décimaux (« 3.5 ») ne coupent pas (pas de blanc après le point). Limite
assumée du MVP : les abréviations (« M. Dupont ») coupent — acceptable à l'oral.
"""

import re

_BOUNDARY = re.compile(r"[.!?…]+(?=\s)|\n")


class SentenceSplitter:
    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        """Ajoute du texte au tampon et renvoie les phrases complètes."""
        self._buffer += text
        sentences: list[str] = []
        while (match := _BOUNDARY.search(self._buffer)) is not None:
            sentence = self._buffer[: match.end()].strip()
            self._buffer = self._buffer[match.end() :].lstrip()
            if sentence:
                sentences.append(sentence)
        return sentences

    def flush(self) -> list[str]:
        """Vide le reliquat en fin de flux (dernière phrase sans ponctuation finale)."""
        remainder = self._buffer.strip()
        self._buffer = ""
        return [remainder] if remainder else []

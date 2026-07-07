"""Nettoyage du texte avant synthèse vocale (bug n°6 du plan).

Séparation stricte texte-à-dire / métadonnées : ce module retire, de façon
EXPLICITE et testée, ce qui ne doit jamais être lu à voix haute :
1. les tags de contrôle `[...]` et `<...>` (émotions, actions : `[joy]`, `<laugh>`) ;
2. les emojis et pictogrammes ;
3. les symboles Markdown (`*`, `_`, "`", `#`, `~`) ;
puis normalise les blancs. Rien d'autre n'est modifié.
"""

import re

# Tags courts sans blanc à l'intérieur, pour ne pas toucher à « 2 < 3 » ou aux crochets légitimes.
_CONTROL_TAGS = re.compile(r"\[[^\[\]\s]{1,25}\]|<[^<>\s]{1,25}>")
_MARKDOWN = re.compile(r"[*_`#~]+")
_EMOJI = re.compile(
    "["
    "\U0001f000-\U0001faff"  # pictogrammes, émotions, symboles divers
    "\U00002600-\U000027bf"  # symboles & dingbats
    "\U0001fb00-\U0001fbff"
    "⬀-⯿"
    "︎️"  # sélecteurs de variante
    "‍"  # zero-width joiner
    "]"
)
_WHITESPACE = re.compile(r"\s+")


def clean_for_tts(text: str) -> str:
    text = _CONTROL_TAGS.sub(" ", text)
    text = _EMOJI.sub("", text)
    text = _MARKDOWN.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def is_speakable(text: str) -> bool:
    """Faux pour ce qui ne se prononce pas (ponctuation seule, restes d'emojis)."""
    return any(char.isalnum() for char in text)

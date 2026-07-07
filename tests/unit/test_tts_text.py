"""Tests du nettoyage texte-à-dire (rien de tout ça ne doit être lu à voix haute)."""

from timbre.core.tts_text import clean_for_tts, is_speakable


def test_control_tags_are_removed():
    assert clean_for_tts("[joy] Bonjour <laugh> toi !") == "Bonjour toi !"


def test_legitimate_comparisons_and_brackets_survive():
    assert clean_for_tts("2 < 3 et [ceci est gardé] aussi") == "2 < 3 et [ceci est gardé] aussi"


def test_emojis_are_removed():
    assert clean_for_tts("Salut 😊 ça va ⭐ ?") == "Salut ça va ?"


def test_markdown_symbols_are_removed():
    assert clean_for_tts("C'est **très** important, `vraiment` #oui") == (
        "C'est très important, vraiment oui"
    )


def test_whitespace_is_normalized():
    assert clean_for_tts("  Trop    d'espaces \n ici  ") == "Trop d'espaces ici"


def test_emoji_only_text_becomes_empty():
    assert clean_for_tts("😊🎉") == ""


def test_punctuation_alone_is_not_speakable():
    assert not is_speakable(".")
    assert not is_speakable("")
    assert is_speakable("Oui.")

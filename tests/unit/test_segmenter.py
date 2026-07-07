"""Tests du découpage en phrases sur flux de tokens."""

from timbre.core.segmenter import SentenceSplitter


def feed_all(tokens: list[str]) -> list[str]:
    splitter = SentenceSplitter()
    sentences = []
    for token in tokens:
        sentences.extend(splitter.feed(token))
    sentences.extend(splitter.flush())
    return sentences


def test_splits_on_punctuation_followed_by_space():
    assert feed_all(["Bonjour", " ! ", "Ça", " va", " ?"]) == ["Bonjour !", "Ça va ?"]


def test_last_sentence_without_trailing_space_comes_from_flush():
    splitter = SentenceSplitter()
    assert splitter.feed("Salut. Comment vas-tu ?") == ["Salut."]
    assert splitter.flush() == ["Comment vas-tu ?"]


def test_decimals_do_not_split():
    assert feed_all(["Il fait 3.5 degrés. ", "Brrr."]) == ["Il fait 3.5 degrés.", "Brrr."]


def test_newline_closes_a_sentence():
    assert feed_all(["Premier point\nDeuxième point"]) == ["Premier point", "Deuxième point"]


def test_ellipsis_and_multiple_marks():
    assert feed_all(["Eh bien... ", "quoi ?! ", "Rien."]) == ["Eh bien...", "quoi ?!", "Rien."]


def test_empty_stream():
    assert feed_all(["", "   "]) == []

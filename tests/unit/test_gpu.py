"""Tests du parsing nvidia-smi (le binaire lui-même est optionnel)."""

from timbre.core.gpu import parse_nvidia_smi


def test_parses_used_and_total():
    assert parse_nvidia_smi("5920, 16376\n") == (5920, 16376)


def test_multi_gpu_takes_first_line():
    assert parse_nvidia_smi("100, 16376\n200, 24000\n") == (100, 16376)


def test_garbage_returns_none():
    assert parse_nvidia_smi("") is None
    assert parse_nvidia_smi("N/A") is None
    assert parse_nvidia_smi("a, b") is None

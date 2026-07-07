"""Tests du contrat de messages : validation stricte, erreurs explicites."""

import pytest

from timbre.protocol.messages import (
    AiChunk,
    ErrorMessage,
    ModelInfo,
    ProtocolError,
    StateChange,
    UserMessage,
    parse_client_message,
)
from timbre.protocol.states import AppState


def test_parse_valid_user_message():
    message = parse_client_message('{"type": "user_message", "text": "bonjour"}')
    assert isinstance(message, UserMessage)
    assert message.text == "bonjour"


def test_parse_rejects_invalid_json():
    with pytest.raises(ProtocolError) as exc_info:
        parse_client_message("pas du json")
    assert exc_info.value.code == "invalid_message"


def test_parse_rejects_unknown_type():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type": "inconnu", "text": "x"}')


def test_parse_rejects_empty_text():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type": "user_message", "text": ""}')


def test_parse_rejects_extra_fields():
    with pytest.raises(ProtocolError):
        parse_client_message('{"type": "user_message", "text": "ok", "extra": 1}')


def test_server_messages_serialize_with_discriminator():
    assert StateChange(state=AppState.LISTENING).model_dump()["type"] == "state_change"
    assert AiChunk(text="salut", last=True).model_dump()["type"] == "ai_chunk"
    assert ErrorMessage(code="x", message="y").model_dump()["type"] == "error"
    assert ModelInfo(model="qwen").model_dump()["type"] == "model_info"


def test_state_change_serializes_enum_as_string():
    assert '"state":"listening"' in StateChange(state=AppState.LISTENING).model_dump_json()

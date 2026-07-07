"""Tests de l'historique de conversation (règle : que du texte réellement émis)."""

from timbre.core.conversation import Conversation


def test_messages_start_with_system_prompt():
    conversation = Conversation("Tu es Timbre.")
    conversation.add_user("Salut")
    assert conversation.to_messages() == [
        {"role": "system", "content": "Tu es Timbre."},
        {"role": "user", "content": "Salut"},
    ]


def test_empty_assistant_turn_is_not_archived():
    conversation = Conversation("sys")
    conversation.add_user("Salut")
    conversation.add_assistant("")
    assert [t["role"] for t in conversation.to_messages()] == ["system", "user"]


def test_partial_assistant_turn_is_archived_verbatim():
    conversation = Conversation("sys")
    conversation.add_user("Raconte")
    conversation.add_assistant("Il était")
    assert conversation.to_messages()[-1] == {"role": "assistant", "content": "Il était"}

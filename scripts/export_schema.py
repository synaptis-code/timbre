"""Exporte le JSON Schema du protocole WebSocket vers schemas/ws-protocol.schema.json.

À relancer après toute modification de timbre/protocol/, puis mettre à jour
ui/src/protocol.ts en conséquence. Le test test_schema_snapshot.py échoue si
le snapshot committé ne correspond plus au code.
"""

import json
from pathlib import Path

from timbre.protocol.messages import client_message_adapter, server_message_adapter

SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "ws-protocol.schema.json"


def build_schema() -> dict[str, object]:
    return {
        "title": "Protocole WebSocket Timbre",
        "client": client_message_adapter.json_schema(),
        "server": server_message_adapter.json_schema(),
    }


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(
        json.dumps(build_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Schéma écrit : {SCHEMA_PATH}")


if __name__ == "__main__":
    main()

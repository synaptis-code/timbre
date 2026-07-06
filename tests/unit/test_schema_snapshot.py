"""Verrouille le contrat front/back : le snapshot committé doit refléter le code.

En cas d'échec : `uv run python scripts/export_schema.py` puis synchroniser
ui/src/protocol.ts avec les changements.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from export_schema import SCHEMA_PATH, build_schema  # noqa: E402


def test_committed_schema_matches_code():
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    current = json.loads(json.dumps(build_schema(), sort_keys=True))
    assert committed == current, (
        "Le protocole a changé : lancer `uv run python scripts/export_schema.py` "
        "et mettre à jour ui/src/protocol.ts."
    )

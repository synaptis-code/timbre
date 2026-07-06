# Timbre

Assistant vocal IA **100 % local** et open source : vous parlez, l'IA comprend, voit votre écran si vous le partagez, et répond avec une personnalité (persona) et une **voix française expressive**. Rien ne quitte jamais votre machine — pas de cloud, pas de compte, pas de télémétrie.

> État : **Phase 1 (squelette)** — backend WebSocket typé + UI minimale connectée. La boucle vocale arrive phase par phase (voir la feuille de route).

## Prérequis

- **Windows** (support Linux/Mac prévu), GPU NVIDIA recommandé pour les phases ASR/TTS.
- **Python ≥ 3.12** et [uv](https://docs.astral.sh/uv/).
- **Node.js ≥ 20** (pour l'UI).
- **[LM Studio](https://lmstudio.ai/)** servant un modèle sur `http://localhost:1234/v1` (requis à partir de la Phase 2).

## Démarrage

```powershell
# Backend (terminal 1)
uv sync
uv run timbre          # démarre sur http://127.0.0.1:8765

# UI (terminal 2)
cd ui
npm install
npm run dev            # ouvre http://localhost:5173
```

Sous Windows, forcer l'UTF-8 évite tout souci d'accents dans la console : `$env:PYTHONUTF8 = "1"`.

## Vérifications qualité

```powershell
uv run ruff check .           # lint
uv run ruff format --check .  # formatage
uv run mypy                   # typage strict
uv run pytest                 # tests unitaires + intégration
```

## Architecture

```
src/timbre/
├─ protocol/    # le contrat : messages WebSocket typés (pydantic) + états
├─ core/        # orchestration & machine à états — ignore le transport
├─ plugins/     # interfaces ASR / LLM / TTS / VAD + implémentations (phases 2-4)
└─ api/         # FastAPI + endpoint /ws — ignore les moteurs
ui/             # Vite + React + TypeScript, connecté en WebSocket
schemas/        # snapshot JSON Schema du protocole (verrouillé par test)
```

Principes non négociables :

- **Zéro plantage silencieux** : toute erreur devient un message `error` visible côté client.
- **Modularité** : changer de moteur TTS/ASR/LLM = un plugin derrière une interface, rien d'autre ne bouge.
- **Local-first** : aucune donnée ne sort de la machine.

Le protocole WebSocket (messages `user_message`, `ai_chunk`, `state_change`, `error`) est défini dans [src/timbre/protocol/messages.py](src/timbre/protocol/messages.py), reflété dans [ui/src/protocol.ts](ui/src/protocol.ts) et verrouillé par le snapshot [schemas/ws-protocol.schema.json](schemas/ws-protocol.schema.json).

## Feuille de route

| Phase | Contenu | État |
|---|---|---|
| 1 | Squelette : WebSocket typé, UI d'état, test d'intégration | ✅ |
| 2 | LLM : streaming LM Studio dans le fil de conversation | ⏳ |
| 3 | TTS : synthèse vocale streaming phrase par phrase | ⏳ |
| 4 | ASR + VAD : boucle vocale complète | ⏳ |
| 5 | Anti-feedback + états mains-libres | ⏳ |
| 6 | Personas robustes (JSON validé, zéro fallback silencieux) | ⏳ |
| 7 | Polish UI | ⏳ |
| 8 | Vision (partage d'écran par tour) | ⏳ |
| 9 | Optimisation latence / VRAM | ⏳ |

## Licence

[Apache-2.0](LICENSE)

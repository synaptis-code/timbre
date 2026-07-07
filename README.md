# Timbre

Assistant vocal IA **100 % local** et open source : vous parlez, l'IA comprend, voit votre écran si vous le partagez, et répond avec une personnalité (persona) et une **voix française expressive**. Rien ne quitte jamais votre machine — pas de cloud, pas de compte, pas de télémétrie.

> État : **Phase 1 (squelette)** — backend WebSocket typé + UI minimale connectée. La boucle vocale arrive phase par phase (voir la feuille de route).

## Prérequis

- **Windows** (support Linux/Mac prévu), GPU NVIDIA recommandé pour les phases ASR/TTS.
- **Python ≥ 3.12** et [uv](https://docs.astral.sh/uv/).
- **Node.js ≥ 20** (pour l'UI).
- **[LM Studio](https://lmstudio.ai/)** avec le serveur local démarré (`lms server start`) et un modèle chargé. **Timbre détecte et utilise automatiquement le modèle chargé** — changer de modèle dans LM Studio suffit, aucun réglage à faire (forçage possible via `TIMBRE_LLM_MODEL`).

## Démarrage

```powershell
# Backend (terminal 1) — l'extra « asr » installe faster-whisper + les DLL CUDA
uv sync --extra asr
uv run --extra asr timbre   # démarre sur http://127.0.0.1:8765

# UI (terminal 2)
cd ui
npm install
npm run dev                 # ouvre http://localhost:5173
```

Clique **Micro ○** dans l'UI et autorise le micro : le mode mains-libres est continu — parle, Timbre transcrit (Whisper sur GPU), répond et parle. Le micro est automatiquement mis en pause pendant que l'IA parle (anti-larsen). Sans GPU NVIDIA : `TIMBRE_ASR_DEVICE=cpu`.

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
- **Local-first** : aucune donnée ne sort de la machine. ⚠️ Exception temporaire assumée : le moteur TTS par défaut du MVP (edge-tts) envoie le texte des réponses au service vocal de Microsoft. Désactivable (`TIMBRE_TTS_ENABLED=0`) ; les moteurs expressifs 100 % locaux le remplaceront (voir feuille de route). Voix configurable via `TIMBRE_TTS_VOICE`.

Le protocole WebSocket (messages `user_message`, `ai_chunk`, `state_change`, `error`) est défini dans [src/timbre/protocol/messages.py](src/timbre/protocol/messages.py), reflété dans [ui/src/protocol.ts](ui/src/protocol.ts) et verrouillé par le snapshot [schemas/ws-protocol.schema.json](schemas/ws-protocol.schema.json).

## Feuille de route

| Phase | Contenu | État |
|---|---|---|
| 1 | Squelette : WebSocket typé, UI d'état, test d'intégration | ✅ |
| 2 | LLM : streaming LM Studio, modèle chargé auto-détecté | ✅ |
| 3 | TTS : synthèse vocale streaming phrase par phrase (edge-tts) | ✅ |
| 4 | ASR + VAD : micro mains-libres → Whisper GPU → boucle vocale complète | ✅ |
| 5 | Anti-feedback + états mains-libres | ⏳ |
| 6 | Personas robustes (JSON validé, zéro fallback silencieux) | ⏳ |
| 7 | Polish UI | ⏳ |
| 8 | Vision (partage d'écran par tour) | ⏳ |
| 9 | Optimisation latence / VRAM | ⏳ |

## Licence

[Apache-2.0](LICENSE)

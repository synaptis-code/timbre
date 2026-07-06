# Timbre — Plan de conception (assistant vocal IA local « épuré »)
> **Nom du projet : Timbre.** Dépôt suggéré : `timbre` (ou `timbre-ai`). Document destiné à une IA de développement. Objectif : concevoir un logiciel neuf, concurrent d'Open-LLM-VTuber, mais **plus optimisé, plus simple, plus robuste**.

---

## 1. Contexte

On veut un **assistant vocal IA 100 % local** : l'utilisateur parle → l'IA comprend, voit son écran si partagé, répond avec une **personnalité** (persona) et une **voix**. Tout tourne sur la machine, sans cloud.

Un projet de référence existe déjà, fonctionne, et a été configuré à fond : **Open-LLM-VTuber**, dans `C:\Users\sacho\Open-LLM-VTuber`. Tu **peux et dois t'en inspirer** (piocher des morceaux de code éprouvés — chemins précis en §8), mais **l'objectif n'est PAS un fork** : c'est un logiciel neuf, plus léger, avec une UI épurée et beaucoup moins de bugs.

### Machine de référence
- Windows 11, GPU **NVIDIA RTX 4080 (16 Go VRAM)**.
- **LM Studio** déjà installé (sert les LLM en local via une API compatible OpenAI sur `http://localhost:1234/v1`).
- Python 3.12 + `uv`, `ffmpeg`, `git` présents.

### Objectifs prioritaires (dans l'ordre)
1. **Open source** : code public, licence permissive (**MIT** ou **Apache-2.0**), archi lisible et documentée, contributions faciles. Aucune dépendance à du code propriétaire.
2. **Backend irréprochable** : entièrement typé (type hints + `mypy`/`pyright`), **testé** (tests unitaires + tests d'intégration sur la boucle vocale), architecture en couches claire, gestion d'erreurs explicite, **zéro plantage silencieux**, logs propres. Le backend est le cœur : il doit être solide comme un roc.
3. **Modularité maximale** :
   - **Changer de modèle de voix (TTS) doit être TRIVIAL** : moteurs TTS en plugins derrière une interface commune, sélection via config/UI, ajout d'un nouveau moteur **sans toucher au reste du code**.
   - **Créer un persona doit être ULTRA-SIMPLE** : éditeur intégré à l'UI (ou format texte simple + validé), impossible à casser, prise en compte immédiate.
   - Idem pour l'ASR et le LLM : backends interchangeables via les mêmes interfaces.
4. **Zéro média personnel embarqué** : contrairement au projet de référence (qui embarque des modèles Live2D, avatars, images, fonds…), ce logiciel **ne contient AUCUN asset image / vidéo / avatar**. L'UI est 100 % code + thème (CSS ; au plus un indicateur d'état vectoriel généré). Dépôt léger, pas de gros binaires média.
5. **Simplicité d'UI** : interface minimaliste, moderne, épurée. Zéro fioriture.
6. **Robustesse** : pas de config fragile, erreurs visibles, isolation des composants.
7. **Optimisation** : faible latence, VRAM maîtrisée, démarrage rapide.
8. **Local-first & vie privée (pilier)** : **rien ne quitte jamais la machine** — LLM, voix, transcription, capture d'écran, historique : tout reste local. Aucun compte, aucune télémétrie, aucun appel cloud par défaut. C'est un principe de design non négociable **et** l'argument différenciant face à Grok/OpenAI/Gemini.

### 🎙️ Exigence phare — des voix expressives et réalistes, 100 % locales

C'est LE cœur de « Timbre ». Objectif de qualité vocale : **se rapprocher des voix de Grok / OpenAI (Advanced Voice) / Gemini** — naturelles, réalistes, et surtout **émotionnellement expressives** :
- rendre des **émotions** : peur, tristesse, joie, colère…
- pouvoir **chuchoter**, **rire**, **crier**.

**Contraintes non négociables :**
- **Français natif obligatoire** : les voix doivent parler un **français naturel** (accent français, pas un anglais accentué ni un français robotique). Le support FR de qualité est un **critère de sélection prioritaire** : un moteur sans bon français est écarté d'office. (L'anglais/le multilingue en plus = bonus, mais le FR n'est pas optionnel.)
- **Voix open source** et **100 % locales** — aucun serveur cloud, aucune donnée qui sort de la machine. Un moteur/serveur d'inférence *local* (llama.cpp, LM Studio, ou un process TTS dédié sur le PC) est OK ; envoyer texte/audio vers le cloud ne l'est PAS.
- Le TTS est un **plugin** : changer de moteur/voix doit rester trivial (cf. objectif #3).

**Honnêteté technique :** égaler *exactement* OpenAI/Gemini en local est à la **frontière** de l'état de l'art, mais plusieurs modèles open source s'en approchent nettement. Candidats à évaluer (2025-2026), du plus adapté à ce besoin :
- **Orpheus 3B** (Apache-2.0) — balises d'émotion **entraînées** (`<laugh>`, `<sigh>`, `<groan>`, `<gasp>`…), multilingue dont FR, local GPU. Le cri/la colère passent par l'intensité + majuscules.
- **Chatterbox / Chatterbox Multilingual** (Resemble AI) — contrôle d'« exagération » émotionnelle + tags `[laugh]`/`[chuckle]`, 23+ langues dont FR, préféré à ElevenLabs dans des tests d'écoute. Local.
- **XTTS-v2 / F5-TTS** — très expressifs, multilingues, expressivité pilotée par un court extrait de référence.
- **Higgs Audio v2**, **Sesame CSM** — conversationnels ultra-naturels (surtout EN pour l'instant).

**Stratégie recommandée :** un moteur **simple par défaut pour le MVP** (edge-tts, faible latence) POUR VALIDER LE PIPELINE, puis un/des moteurs **expressifs** branchables via l'interface plugin, avec pour chacun un **curseur qualité / latence / VRAM clairement documenté**. L'expressivité coûte en latence et en VRAM → garder le pipeline **streaming phrase-par-phrase** pour compenser. Prévoir un mapping propre « émotion demandée → balises/paramètres du moteur » (ex. `colère` → intensité haute + `!`, `rire` → `<laugh>`), défini une seule fois et réutilisé par tous les moteurs.

---

## 2. Architecture qui MARCHE (à reprendre comme socle)

Le pipeline validé sur le projet de référence, à garder :

```
🎤 Micro → VAD (détection de parole) → ASR (faster-whisper, GPU)
        → texte → LLM (LM Studio, API OpenAI) [+ image écran si partagé]
        → réponse en streaming → découpage en phrases
        → TTS (edge-tts) phrase par phrase → 🔊 lecture audio
```

Composants et choix par défaut (tous locaux) :
- **LLM** : LM Studio, endpoint OpenAI-compatible (`/v1/chat/completions`). Modèle par défaut : un modèle **« Instruct » multimodal non-raisonnant** (ex. `qwen2.5-vl-7b-instruct-abliterated`). Le format multimodal (image + texte) passe tel quel à LM Studio.
- **ASR** : `faster-whisper` (`large-v3-turbo`) sur GPU.
- **TTS** : `edge-tts` (voix FR neurales, faible latence) — mais **derrière une interface abstraite** pour brancher d'autres moteurs plus tard.
- **VAD** : `silero-vad` (ou VAD navigateur) pour le mains-libres.
- **Vision** : capture d'écran envoyée **par tour** au LLM multimodal (pas de flux continu).

---

## 3. Les bugs/frictions RÉELS à éliminer (le vrai différenciateur)

Ces problèmes ont été rencontrés en vrai sur le projet de référence. **Les corriger by-design est la raison d'être du nouveau logiciel.**

1. **Personas fragiles (YAML à indentation).** Éditer un persona à la main cassait tout le fichier (une ligne mal alignée = fichier illisible), et un seul fichier cassé **plantait le chargement de tous les personas**.
   → **À faire** : format de persona **robuste** (JSON validé par schéma, ou éditeur intégré dans l'UI). Validation au chargement, **isolation** (un persona invalide n'impacte pas les autres), et **message d'erreur clair** dans l'UI.

2. **Fallback silencieux.** Quand un persona ne se chargeait pas, l'app basculait **en silence** sur le persona par défaut → l'utilisateur croyait que son prompt marchait alors que non.
   → **À faire** : **jamais de fallback silencieux**. Si un persona est invalide, le dire explicitement dans l'UI (badge rouge + raison).

3. **Mémoire de conversation corrompue.** Sous forte latence TTS / interruptions, l'historique stockait mal les réponses de l'IA → l'IA « inventait » ce qu'elle avait dit avant (réponses incohérentes).
   → **À faire** : ne stocker dans l'historique que le **texte réellement généré**, de façon atomique, indépendamment de l'état de lecture audio. Gérer proprement les interruptions (marquer « interrompu » sans corrompre le tour précédent).

4. **VRAM saturée.** Charger plusieurs modèles (LLM chat + LLM voix + Whisper) sur 16 Go saturait la VRAM (→ lenteurs, plantages de la chaîne de conversation).
   → **À faire** : **un seul modèle GPU lourd par défaut**. Afficher la VRAM utilisée dans l'UI. Réglages explicites (contexte, parallélisme). Whisper basculable CPU/GPU en un clic.

5. **Latence TTS élevée / modèles à raisonnement.** Les LLM « thinking » (reasoning) consomment des centaines de tokens avant de répondre → lenteur et réponses vides. Certains moteurs TTS (Orpheus) étaient trop lents.
   → **À faire** : détecter/avertir si le modèle est « raisonnant » (lire `reasoning_content` séparément, ne pas l'envoyer au TTS). TTS **streaming phrase-par-phrase** pour une latence perçue minimale. Interface TTS pluggable.

6. **Tags de contrôle qui fuient dans la voix/texte.** Des mots-clés d'expression (`[joy]`, `[sadness]`, `<laugh>`) apparaissaient dans les réponses ou étaient lus à voix haute.
   → **À faire** : séparation stricte **texte-à-dire** / **métadonnées de contrôle**. Un pipeline de nettoyage TTS **explicite et testé** (config claire de ce qui est retiré).

7. **Capture d'écran fragile.** Quand l'utilisateur arrêtait le partage, l'app continuait à capturer → `InvalidStateError` en boucle.
   → **À faire** : écouter la fin du `MediaStreamTrack`, arrêter proprement la capture, ré-acquérir le flux à la demande.

8. **Micro pénible.** Il fallait recliquer sur le micro à chaque tour ; risque de boucle de feedback (le micro entend la voix de l'IA).
   → **À faire** : mode mains-libres **continu par défaut** (VAD), **mute automatique du micro pendant la lecture TTS** (anti-feedback), états visuels ultra-clairs (écoute / réflexion / parle).

9. **Logs bufferisés/illisibles.** Impossible de diagnostiquer en direct.
   → **À faire** : logs **non bufferisés**, structurés, avec un petit panneau de logs/diagnostic dans l'UI (optionnel).

10. **Live2D = complexité inutile.** L'avatar Live2D était une grosse source de complexité/bugs pour un usage vocal.
    → **À faire** : **pas de Live2D**. Une UI épurée avec au plus un indicateur d'état animé (waveform/orbe). Avatar optionnel très plus tard.

---

## 4. UI cible (épurée)

Principes : **une seule fenêtre, minimaliste, sombre par défaut, zéro clutter**.

Écran principal :
- Un **fil de conversation** propre (bulles user/IA, texte des transcriptions et réponses).
- Un **indicateur d'état central** unique et clair : `● En écoute` / `… Réflexion` / `🔊 Parle` / `Idle`.
- Une **barre d'action minimale** : micro (mute/unmute), partage d'écran (on/off), stop/interrompre.
- Un **sélecteur de persona** simple (dropdown), avec statut (vert = OK, rouge = invalide + raison).
- Réglages dans un panneau **repliable** (pas une usine à gaz) : modèle LLM, voix TTS, langue, mic auto, device Whisper.

À NE PAS faire : onglets multiples, avatars 3D, menus imbriqués, options obscures en vrac.

**Piste techno UI** (au choix de l'IA de dev, viser le plus simple/propre) :
- **Option A (recommandée pour l'épuré natif)** : app desktop **Tauri** (Rust + webview) → fenêtre native, accès micro propre, pas d'onglet navigateur ni DevTools qui traînent, petit binaire.
- **Option B (plus rapide à livrer)** : SPA web légère (**Vite + Svelte ou React + TypeScript**) servie en local, communication **WebSocket**.
Dans les deux cas : composant audio en Web Audio API, WebSocket pour le streaming des événements/audio.

---

## 5. Stack technique recommandée

**Backend (Python)** — garder Python pour l'écosystème ML (faster-whisper, silero) :
- `FastAPI` + `uvicorn` (WebSocket pour le streaming temps réel).
- `faster-whisper` (ASR GPU) — voir §8 pour le chargement des DLL CUDA sous Windows.
- `edge-tts` (TTS par défaut) derrière une interface `TTSBackend` abstraite.
- `silero-vad` (VAD serveur) OU VAD côté client.
- Client LLM = simple appels HTTP à l'API OpenAI de LM Studio (SDK `openai` ou `httpx`), en **streaming**.
- Découpage en phrases : `pysbd` (ou regex simple) pour le streaming TTS.
- Gestion d'env : `uv`. **Installer hors OneDrive** (les venvs + modèles ne doivent jamais être synchronisés dans le cloud).

**Frontend** : voir §4 (Tauri ou Vite+Svelte/React+TS).

**Contrats clés (à définir proprement)** :
- Interface `LLMBackend` : `stream_chat(messages, images) -> AsyncIterator[str]`.
- Interface `ASRBackend` : `transcribe(audio) -> str`.
- Interface `TTSBackend` : `synthesize(text, voice) -> audio` (streaming si possible).
- Interface `VAD` : événements `speech_start` / `speech_end`.
- Protocole WebSocket : messages typés (`user_transcript`, `ai_chunk`, `state_change`, `error`, …).

---

## 6. Périmètre

### MVP (à livrer en premier)
- Boucle vocale complète : VAD → ASR → LLM (LM Studio) → TTS (edge-tts) → lecture.
- Mains-libres continu + mute anti-feedback.
- 1 persona par défaut + sélecteur, format robuste.
- UI épurée avec indicateur d'état.
- Config minimale (modèle, voix, langue).

### V2
- Vision (partage d'écran par tour) vers LLM multimodal, avec gestion propre de la fin de flux.
- Éditeur de persona dans l'UI (plus de fichier à la main).
- Panneau VRAM/diagnostic.
- TTS pluggable (brancher d'autres moteurs).

### Plus tard (optionnel)
- Mémoire longue / historique cherchable.
- Interruption « barge-in » pendant que l'IA parle.
- Avatar léger optionnel.

---

## 7. Séquence de développement (phases)

1. **Squelette** : backend FastAPI + WebSocket + frontend vide qui se connecte et affiche un état.
2. **LLM** : brancher LM Studio, streaming texte dans le fil de conversation (au clavier d'abord, sans voix).
3. **TTS** : edge-tts en streaming phrase-par-phrase sur la réponse.
4. **ASR + VAD** : micro → transcription → envoi au LLM. Boucle vocale complète.
5. **Anti-feedback + états** : mute pendant TTS, indicateurs d'état, mains-libres continu.
6. **Personas robustes** : format validé, sélecteur, pas de fallback silencieux.
7. **Polish UI** : épuration, thème, transitions.
8. **Vision** : partage d'écran par tour (gestion propre de la fin de flux).
9. **Optimisation** : mesure latence/VRAM, réglages, device Whisper CPU/GPU.

Chaque phase = testable de bout en bout avant la suivante.

---

## 8. Code réutilisable & où le trouver

**Principe général — ne réinvente pas la roue.** Avant de coder un composant non trivial (streaming audio WebSocket, wrapper VAD/ASR/TTS, découpage de phrases, gestion d'un moteur TTS, capture d'écran, mute anti-feedback…), **cherche activement sur GitHub et Hugging Face** s'il existe déjà une brique open source propre à réutiliser ou adapter. Si un projet fait bien une partie du boulot, récupères-en les morceaux utiles pour **gagner du temps** — à deux conditions systématiques :
1. **Vérifier la licence** (compatible avec MIT/Apache-2.0 pour que « Timbre » reste réellement open source) et créditer si besoin ;
2. **Comprendre et adapter** le code repris (pas de copier-coller aveugle) pour qu'il respecte l'archi et les standards de qualité du projet (typé, testé).

S'appuyer sur l'existant est **encouragé** partout où ça fait gagner du temps sans dette technique.

> ⚠️ **Le projet de référence sera peut-être supprimé de la machine.** Pour un projet open source propre, privilégier une approche **clean-room** : s'inspirer des idées/de l'archi ci-dessous, mais **réécrire** (pas de copier-coller de code sous une autre licence). Si le dossier a été supprimé, ignore les chemins ; les concepts restent valables.

Racine (si encore présente) : `C:\Users\sacho\Open-LLM-VTuber`. À **lire pour s'inspirer** (réécrire, ne pas copier tel quel) :

- **Client LLM OpenAI streaming** (passe les images multimodales telles quelles) :
  `src\open_llm_vtuber\agent\stateless_llm\openai_compatible_llm.py`
- **Construction des messages multimodaux** (format `image_url` / `data:image` pour la vision) :
  `src\open_llm_vtuber\agent\agents\basic_memory_agent.py` (méthode `_to_messages`).
- **ASR faster-whisper** :
  `src\open_llm_vtuber\asr\faster_whisper_asr.py`
- **⚠️ Astuce CUDA Windows indispensable** : faster-whisper GPU a besoin des DLL `cublas`/`cudnn` absentes par défaut. Solution appliquée : installer les wheels `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`, puis un `sitecustomize.py` dans le venv qui fait `os.add_dll_directory(...)` sur les dossiers `nvidia\*\bin`. Voir `C:\Users\sacho\Open-LLM-VTuber\.venv\Lib\site-packages\sitecustomize.py`. **À reprendre tel quel.**
- **Interfaces + implémentations TTS** (edge-tts, openai-compatible) :
  `src\open_llm_vtuber\tts\` (`tts_interface.py`, `edge_tts.py`, `openai_tts.py`).
- **Nettoyage du texte avant TTS** (à repenser, mais bonne base) :
  `src\open_llm_vtuber\utils\tts_preprocessor.py`.
- **VAD silero** :
  `src\open_llm_vtuber\vad\silero.py`.
- **Config de référence** (montre tous les réglages possibles) :
  `C:\Users\sacho\Open-LLM-VTuber\conf.yaml` et `config_templates\conf.default.yaml`.

> Note licence : Open-LLM-VTuber a sa propre licence (voir `LICENSE`). S'inspirer de l'archi et des idées est OK ; pour de la reprise de code, vérifier la compatibilité de licence avant de publier.

### Projets externes à consulter (facultatif — purement informatif)

Plusieurs projets open source sont d'excellentes sources d'inspiration. **Rien d'obligatoire**, à regarder si utile :

- **NVIDIA PersonaPlex** ⭐ — le plus proche de « Timbre » : assistant vocal **temps réel, full-duplex, speech-to-speech**, avec **contrôle de persona** par prompt texte + **conditionnement de la voix** par audio. Open source. → `github.com/NVIDIA/personaplex` · modèle `huggingface.co/nvidia/personaplex-7b-v1`.
- **NVIDIA Project G-Assist** — assistant IA **local sur RTX** avec un **système de plugins en JSON** (déposer un fichier de config = nouvelle capacité). Inspirant pour la modularité persona/outils.
- **NVIDIA voice-agent-examples** — patterns d'architecture d'agents vocaux temps réel (framework **Pipecat**). → `github.com/NVIDIA/voice-agent-examples`.
- **NVIDIA NeMo Speech** — modèles ASR/TTS open (Parakeet/Canary en ASR multilingue, **Magpie TTS** / Nemotron speech) à considérer comme moteurs (cf. §1 « voix »). → `github.com/NVIDIA-NeMo/Speech`.

**Pour l'UI & le système de chat :**
- **AnythingLLM** (Mintplex Labs, licence **MIT**) ⭐ — appli open source de chat avec LLM locaux, qui **se connecte à LM Studio**. Stack **ViteJS + React** (frontend) + **Node/Express** (backend). Excellente référence pour l'**UI de chat** et l'UX : mise en page des bulles, **streaming** des réponses, gestion des conversations/historique, réglages des providers. Licence MIT = code réutilisable. → `github.com/Mintplex-Labs/anything-llm`.

---

## 9. Definition of Done (qualité)

Le logiciel est « bon » quand :
- Démarrage → conversation vocale en **< 15 s**, en **1 exécutable/commande** (pas 3 fenêtres à garder ouvertes).
- Latence perçue (fin de parole → 1ers mots de l'IA) **< 3 s** en local.
- **Aucun plantage silencieux** : toute erreur (persona, modèle injoignable, VRAM) est visible et explicite dans l'UI.
- Créer un persona ne peut **jamais** casser l'app ni les autres personas.
- Le micro reste en mains-libres sans reclic, sans boucle de feedback.
- VRAM du setup par défaut **< 10 Go** (marge sur 16 Go).
- UI : un débutant comprend l'écran principal en **5 secondes**.

---

## 10. Points d'attention divers (leçons de terrain)
- **Ne jamais installer dans OneDrive** (venvs/modèles = plusieurs Go, sync = casse). Dossier local dédié.
- **Encodage UTF-8 partout** (Windows console = cp1252 → crash sur emoji/accents ; forcer `PYTHONUTF8=1`).
- **Modèles « Instruct » non-raisonnants** par défaut pour le vocal (vérifier `reasoning_tokens: 0`).
- **edge-tts ne fait pas d'émotions** (rire/colère) : ne pas promettre ça sur ce moteur. Pour des émotions FR, prévoir un backend TTS dédié plus tard (curseur clairement documenté).
- **CosyVoice2 ne gère pas bien le français** ; edge-tts (FR neural) est le bon défaut simple.

---

## 11. Format de persona (schéma)

Objectif : créer/éditer un persona doit être **trivial et impossible à casser** (l'inverse du YAML fragile du projet de référence). Format recommandé : **JSON validé par un schéma** (et/ou édité via l'UI). Exemple :

```json
{
  "id": "lea",
  "name": "Léa",
  "language": "fr",
  "system_prompt": "Tu es Léa, une assistante française chaleureuse et concise. Tu réponds en phrases courtes, parlées.",
  "voice": {
    "engine": "edge-tts",
    "voice_id": "fr-FR-VivienneMultilingualNeural",
    "params": { "rate": 1.0, "pitch": 0 }
  },
  "greeting": "Salut ! Je t'écoute.",
  "temperature": 0.8
}
```

Règles :
- **Validation à la lecture** (JSON Schema / pydantic). Un persona invalide → **erreur explicite dans l'UI**, isolé, **sans casser les autres** et **sans fallback silencieux**.
- `voice.engine` référence un plugin TTS (cf. §1 modularité) : changer de voix = changer 2 champs.
- **Rechargement à chaud**, effet immédiat.
- Fournir 1-2 personas d'exemple, **sans aucun média** (pas d'avatar/image).

---

## 12. Non-objectifs (pour rester épuré)

Ce que Timbre **ne fera PAS** (au moins pas au début), pour rester simple, rapide et maintenable :
- ❌ Pas de **RAG / gestion de documents** (ce n'est pas AnythingLLM).
- ❌ Pas de **multi-utilisateurs**, comptes ou permissions.
- ❌ Pas de **cloud, de sync, ni de télémétrie**.
- ❌ Pas d'**avatar 3D / Live2D / média embarqué**.
- ❌ Pas d'**application mobile** (desktop only).
- ❌ Pas d'**entraînement/fine-tuning** dans l'app (on consomme des modèles existants).
- ❌ Pas de **marketplace de plugins** complexe au départ (juste des plugins locaux simples).

En cas de doute sur un ajout : le peser contre l'objectif « épuré ». Si ça n'est pas essentiel → **ne pas l'ajouter**.

---

## 13. Packaging, installation & multiplateforme

- **Installation en 1 action** : l'utilisateur final lance Timbre via un **installeur** ou **une seule commande**. Pas 3 fenêtres à garder ouvertes (leçon directe du projet de référence).
- **Prérequis externes clairs** : un serveur LLM local (LM Studio ou équivalent) doit tourner. Le **détecter et guider** si absent (message clair, jamais un crash).
- **Cible plateforme (à décider)** — recommandation : **Windows d'abord** (machine cible), avec une archi qui n'empêche pas Mac/Linux ensuite.
  - ⚠️ L'astuce de chargement des **DLL CUDA** (cf. §8) est **spécifique Windows**. Sur Linux/Mac la gestion GPU de faster-whisper diffère → **isoler ce code par plateforme**.
- **Distribution** : dépôt GitHub public, **releases** avec binaire/installeur, **README** clair (prérequis, install, lancement), licence MIT/Apache, `CONTRIBUTING.md`.

---

## 14. Budget de latence (cible : réponse perçue < 3 s)

Répartition cible, de la fin de parole de l'utilisateur au **1er mot** de l'IA :

| Étape | Cible |
|---|---|
| VAD (détection fin de parole) | ~200-500 ms |
| ASR (faster-whisper GPU, phrase courte) | < 500 ms |
| LLM — 1er token (LM Studio, modèle Instruct) | < 800 ms |
| TTS — 1re phrase (moteur simple) | < 1 s |
| **Total perçu (1ers mots)** | **< 3 s** |

Leviers : **streaming partout** (LLM token par token, TTS phrase par phrase — ne jamais attendre la fin), modèles **non-raisonnants**, modèles gardés **chauds** en VRAM. **Mesurer et afficher** ces temps en mode debug pour pouvoir optimiser. Les moteurs de voix expressifs (cf. §1) coûtent plus cher → le streaming phrase-par-phrase est ce qui garde la latence perçue acceptable.

import type { MicVAD } from "@ricky0123/vad-web";
import { encodeWavBase64 } from "./wav";

const VAD_SAMPLE_RATE = 16000;
const START_TIMEOUT_MS = 15000;

export interface MicHandlers {
  /** Une prise de parole complète, encodée en WAV base64. */
  onSpeech: (wavB64: string) => void;
  /** L'utilisateur commence à parler (sert au barge-in : couper la voix de l'IA). */
  onSpeechStart?: () => void;
  /** Fausse détection (bruit court) : annuler l'éventuel barge-in. */
  onMisfire?: () => void;
  /** Micro réellement actif ou non (après permission navigateur). */
  onStatus: (on: boolean) => void;
  onError: (message: string) => void;
}

/** Micro mains-libres : VAD silero dans le navigateur (assets locaux, /vad/).
 *
 * Le VAD reste actif pendant que l'IA parle : c'est ce qui permet de lui
 * couper la parole (barge-in). L'anti-larsen repose sur l'annulation d'écho
 * du navigateur (echoCancellation) — l'IA ne s'entend pas elle-même.
 */
export class MicController {
  private readonly handlers: MicHandlers;
  private vad: MicVAD | null = null;
  private wantedOn = false;
  private starting = false;

  constructor(handlers: MicHandlers) {
    this.handlers = handlers;
  }

  async toggle(): Promise<void> {
    if (this.wantedOn) {
      this.wantedOn = false;
      this.vad?.pause();
      this.handlers.onStatus(false);
      return;
    }
    this.wantedOn = true;
    if (this.vad === null) {
      if (this.starting) return;
      this.starting = true;
      // Import dynamique : le runtime VAD/ONNX (~400 Ko) n'est chargé qu'au
      // premier usage du micro — démarrage de l'app plus léger.
      const vadPromise = import("@ricky0123/vad-web").then((vadModule) =>
        vadModule.MicVAD.new({
          model: "v5",
          baseAssetPath: "/vad/",
          onnxWASMBasePath: "/vad/",
          // Annulation d'écho explicite : indispensable au barge-in (l'IA ne
          // doit pas s'entendre elle-même via les enceintes).
          getStream: () =>
            navigator.mediaDevices.getUserMedia({
              audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
            }),
          onSpeechStart: () => {
            if (this.wantedOn) this.handlers.onSpeechStart?.();
          },
          onVADMisfire: () => {
            if (this.wantedOn) this.handlers.onMisfire?.();
          },
          onSpeechEnd: (audio: Float32Array) => {
            if (this.wantedOn) {
              this.handlers.onSpeech(encodeWavBase64(audio, VAD_SAMPLE_RATE));
            }
          },
        }),
      );
      try {
        // Jamais de blocage silencieux : si l'init pend (permission ignorée,
        // navigateur récalcitrant), on le dit et on libère le bouton.
        this.vad = await Promise.race([
          vadPromise,
          new Promise<never>((_, reject) => {
            setTimeout(
              () => reject(new Error("le démarrage du micro a expiré — réessaie")),
              START_TIMEOUT_MS,
            );
          }),
        ]);
      } catch (error) {
        // Si l'init aboutit finalement après le timeout : pas de micro fantôme.
        vadPromise.then((vad) => vad.destroy()).catch(() => undefined);
        this.wantedOn = false;
        const isNotAllowed =
          (error instanceof DOMException && error.name === "NotAllowedError") ||
          (error instanceof Error && (error.name === "NotAllowedError" || error.message.includes("Permission denied") || error.message.includes("Permission dismissed")));
        if (isNotAllowed) {
          this.handlers.onStatus(false);
          return;
        }
        this.handlers.onError(
          `Micro indisponible : ${error instanceof Error ? error.message : String(error)}`,
        );
        return;
      } finally {
        this.starting = false;
      }
    }
    this.vad.start();
    this.handlers.onStatus(true);
  }

  async setStatus(on: boolean): Promise<void> {
    if (this.wantedOn === on) return;
    await this.toggle();
  }

  destroy(): void {
    this.wantedOn = false;
    this.vad?.destroy();
    this.vad = null;
  }
}

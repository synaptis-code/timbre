import { MicVAD } from "@ricky0123/vad-web";
import { encodeWavBase64 } from "./wav";

const VAD_SAMPLE_RATE = 16000;
const START_TIMEOUT_MS = 15000;

export interface MicHandlers {
  /** Une prise de parole complète, encodée en WAV base64. */
  onSpeech: (wavB64: string) => void;
  /** Micro réellement actif ou non (après permission navigateur). */
  onStatus: (on: boolean) => void;
  onError: (message: string) => void;
}

/** Micro mains-libres : VAD silero dans le navigateur (assets locaux, /vad/).
 *
 * Anti-feedback : `setTtsPlaying(true)` met le VAD en pause pendant que l'IA
 * parle, pour que le micro n'entende pas sa voix (bug n°8 du plan).
 */
export class MicController {
  private vad: MicVAD | null = null;
  private wantedOn = false;
  private ttsPlaying = false;
  private starting = false;

  private readonly handlers: MicHandlers;

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
      const vadPromise = MicVAD.new({
        model: "v5",
        baseAssetPath: "/vad/",
        onnxWASMBasePath: "/vad/",
        onSpeechEnd: (audio: Float32Array) => {
          if (this.wantedOn && !this.ttsPlaying) {
            this.handlers.onSpeech(encodeWavBase64(audio, VAD_SAMPLE_RATE));
          }
        },
      });
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
        this.handlers.onError(
          `Micro indisponible : ${error instanceof Error ? error.message : String(error)}`,
        );
        return;
      } finally {
        this.starting = false;
      }
    }
    this.applyPauseState();
    this.handlers.onStatus(true);
  }

  /** Pause anti-feedback pendant la lecture TTS. */
  setTtsPlaying(playing: boolean): void {
    this.ttsPlaying = playing;
    this.applyPauseState();
  }

  destroy(): void {
    this.wantedOn = false;
    this.vad?.destroy();
    this.vad = null;
  }

  private applyPauseState(): void {
    if (this.vad === null) return;
    if (this.wantedOn && !this.ttsPlaying) this.vad.start();
    else this.vad.pause();
  }
}

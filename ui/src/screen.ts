const MAX_WIDTH = 1280;
const JPEG_QUALITY = 0.7;

export interface ScreenHandlers {
  onStatus: (on: boolean) => void;
  onError: (message: string) => void;
}

/** Partage d'écran « par tour » : on garde le flux ouvert, mais une seule
 * image est capturée au moment où l'utilisateur parle ou écrit — pas de
 * flux continu vers le LLM (§2 du plan).
 *
 * Fin de flux propre (bug n°7) : si l'utilisateur arrête le partage via la
 * barre du navigateur, l'événement `ended` du MediaStreamTrack coupe tout
 * proprement ; toute capture sur un flux mort est refusée sans erreur en boucle.
 */
export class ScreenShare {
  private readonly handlers: ScreenHandlers;
  private stream: MediaStream | null = null;
  private video: HTMLVideoElement | null = null;

  constructor(handlers: ScreenHandlers) {
    this.handlers = handlers;
  }

  get isOn(): boolean {
    return this.stream !== null;
  }

  async toggle(): Promise<void> {
    if (this.stream !== null) {
      this.stop();
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
    } catch (error) {
      const isNotAllowed =
        (error instanceof DOMException && error.name === "NotAllowedError") ||
        (error instanceof Error && error.name === "NotAllowedError");
      if (isNotAllowed) {
        return;
      }
      this.handlers.onError(
        `Partage d'écran impossible : ${error instanceof Error ? error.message : String(error)}`,
      );
      return;
    }
    const video = document.createElement("video");
    video.srcObject = stream;
    video.muted = true;
    try {
      await video.play();
    } catch {
      // la première frame arrivera au plus tard à la capture
    }
    stream.getVideoTracks()[0]?.addEventListener("ended", () => this.stop());
    this.stream = stream;
    this.video = video;
    this.handlers.onStatus(true);
  }

  stop(): void {
    if (this.stream === null) return;
    for (const track of this.stream.getTracks()) track.stop();
    if (this.video !== null) this.video.srcObject = null;
    this.stream = null;
    this.video = null;
    this.handlers.onStatus(false);
  }

  /** Capture l'image courante (data-URL JPEG ≤ 1280 px), ou null si indisponible. */
  captureFrame(): string | null {
    const track = this.stream?.getVideoTracks()[0];
    if (this.video === null || track === undefined || track.readyState !== "live") {
      this.stop(); // flux mort : on coupe proprement au lieu d'échouer en boucle
      return null;
    }
    const width = this.video.videoWidth;
    const height = this.video.videoHeight;
    if (width === 0 || height === 0) return null;
    const scale = Math.min(1, MAX_WIDTH / width);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const context = canvas.getContext("2d");
    if (context === null) return null;
    context.drawImage(this.video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", JPEG_QUALITY);
  }
}

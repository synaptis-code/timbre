/** File de lecture audio : les phrases arrivent en streaming et sont jouées
 * dans l'ordre, l'une après l'autre. */
export class AudioQueue {
  private queue: string[] = []; // object URLs en attente
  private current: HTMLAudioElement | null = null;

  private readonly onActiveChange?: (active: boolean) => void;

  /** `onActiveChange(true)` au début d'une lecture, `false` quand la file est vide
   * (sert au mute anti-feedback du micro). */
  constructor(onActiveChange?: (active: boolean) => void) {
    this.onActiveChange = onActiveChange;
  }

  get isActive(): boolean {
    return this.current !== null;
  }

  /** Pause/reprise sans vider la file (barge-in : l'utilisateur commence à parler). */
  pause(): void {
    this.current?.pause();
  }

  resume(): void {
    void this.current?.play().catch(() => undefined);
  }

  enqueue(audioB64: string, format: "mp3" | "wav" = "mp3"): void {
    const bytes = Uint8Array.from(atob(audioB64), (char) => char.charCodeAt(0));
    const mimeType = format === "wav" ? "audio/wav" : "audio/mpeg";
    const url = URL.createObjectURL(new Blob([bytes], { type: mimeType }));
    this.queue.push(url);
    if (this.current === null) {
      this.onActiveChange?.(true);
      this.playNext();
    }
  }

  /** Coupe la lecture et vide la file (déconnexion, interruption). */
  stop(): void {
    for (const url of this.queue) URL.revokeObjectURL(url);
    this.queue = [];
    if (this.current !== null) {
      this.current.pause();
      this.current = null;
      this.onActiveChange?.(false);
    }
  }

  private playNext(): void {
    const url = this.queue.shift();
    if (url === undefined) {
      this.current = null;
      this.onActiveChange?.(false);
      return;
    }
    const audio = new Audio(url);
    this.current = audio;
    const advance = () => {
      URL.revokeObjectURL(url);
      this.playNext();
    };
    audio.onended = advance;
    audio.onerror = () => {
      console.error("Lecture audio échouée pour une phrase — on passe à la suivante.");
      advance();
    };
    audio.play().catch((error: unknown) => {
      console.error("Lecture audio bloquée (autoplay ?) :", error);
      advance();
    });
  }
}

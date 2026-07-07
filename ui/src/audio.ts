/** File de lecture audio : les phrases arrivent en streaming et sont jouées
 * dans l'ordre, l'une après l'autre. */
export class AudioQueue {
  private queue: string[] = []; // object URLs en attente
  private current: HTMLAudioElement | null = null;

  enqueue(audioB64: string, mimeType = "audio/mpeg"): void {
    const bytes = Uint8Array.from(atob(audioB64), (char) => char.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: mimeType }));
    this.queue.push(url);
    if (this.current === null) this.playNext();
  }

  /** Coupe la lecture et vide la file (déconnexion, interruption). */
  stop(): void {
    for (const url of this.queue) URL.revokeObjectURL(url);
    this.queue = [];
    if (this.current !== null) {
      this.current.pause();
      this.current = null;
    }
  }

  private playNext(): void {
    const url = this.queue.shift();
    if (url === undefined) {
      this.current = null;
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

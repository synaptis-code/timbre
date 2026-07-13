/** Aperçu audio d'une voix : récupère un court échantillon synthétisé côté serveur
 * et le joue. Un seul aperçu à la fois (le précédent est coupé). */
import { API_BASE } from "./api";

let current: HTMLAudioElement | null = null;

export function stopVoicePreview(): void {
  if (current !== null) {
    current.pause();
    current = null;
  }
}

export async function previewVoice(voiceId: string): Promise<void> {
  stopVoicePreview();
  const response = await fetch(`${API_BASE}/api/voices/${encodeURIComponent(voiceId)}/preview`);
  if (!response.ok) {
    throw new Error(`Aperçu indisponible (${response.status}).`);
  }
  // Le Content-Type (audio/wav ou audio/mpeg) est porté par la réponse.
  const url = URL.createObjectURL(await response.blob());
  const audio = new Audio(url);
  current = audio;
  const cleanup = () => {
    URL.revokeObjectURL(url);
    if (current === audio) current = null;
  };
  audio.onended = cleanup;
  audio.onerror = cleanup;
  await audio.play();
}

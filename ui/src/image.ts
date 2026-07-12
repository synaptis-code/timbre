const MAX_WIDTH = 1280;
const JPEG_QUALITY = 0.85;

/** Normalise une image (collée ou uploadée) pour le protocole : le backend
 * n'accepte que JPEG/PNG/WebP en data-URL ≤ 8 Mo. On convertit donc tout
 * format décodable (GIF, BMP, AVIF…) en JPEG et on borne la taille — même
 * logique que la capture d'écran (screen.ts). */
export function normalizeImageDataUrl(dataUrl: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const scale = Math.min(1, MAX_WIDTH / image.naturalWidth);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      const context = canvas.getContext("2d");
      if (context === null) {
        reject(new Error("canvas indisponible"));
        return;
      }
      // Fond blanc : le JPEG n'a pas de transparence (PNG/GIF transparents).
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", JPEG_QUALITY));
    };
    image.onerror = () => reject(new Error("image illisible"));
    image.src = dataUrl;
  });
}

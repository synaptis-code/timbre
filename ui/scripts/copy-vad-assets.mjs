// Copie les assets du VAD (modèle silero + runtime onnx + worklet) vers
// public/vad/ pour qu'ils soient servis en LOCAL, en dev comme en build
// (local-first : jamais de CDN). Lancé par predev/prebuild.
import { cpSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const uiDir = join(dirname(fileURLToPath(import.meta.url)), "..");
const dest = join(uiDir, "public", "vad");
mkdirSync(dest, { recursive: true });

const sources = [
  [
    join(uiDir, "node_modules", "@ricky0123", "vad-web", "dist"),
    (f) => f.endsWith(".onnx") || f === "vad.worklet.bundle.min.js",
  ],
  [
    join(uiDir, "node_modules", "onnxruntime-web", "dist"),
    (f) => f.startsWith("ort-wasm-simd-threaded") && (f.endsWith(".wasm") || f.endsWith(".mjs")),
  ],
];

let count = 0;
for (const [srcDir, keep] of sources) {
  for (const file of readdirSync(srcDir).filter(keep)) {
    cpSync(join(srcDir, file), join(dest, file));
    count++;
  }
}
console.log(`[vad] ${count} assets copiés vers public/vad/`);

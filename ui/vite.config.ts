import { createReadStream, existsSync } from 'node:fs'
import { dirname, extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const uiDir = dirname(fileURLToPath(import.meta.url))

const MIME: Record<string, string> = {
  '.mjs': 'text/javascript',
  '.js': 'text/javascript',
  '.wasm': 'application/wasm',
  '.onnx': 'application/octet-stream',
}

// Les assets du VAD (modèle silero + runtime onnx + worklet) sont copiés vers
// public/vad/ par scripts/copy-vad-assets.mjs (predev/prebuild) et servis en
// LOCAL — jamais depuis un CDN (local-first).
//
// En dev, le runtime onnx charge son module via import() dynamique : Vite
// intercepte la requête (`?import`) et refuse les fichiers de public/ comme
// modules. Ce middleware sert /vad/* directement, avant le pipeline de Vite.
// En build, public/ est copié tel quel dans dist/ : rien à faire.
function serveVadAssets(): Plugin {
  return {
    name: 'timbre:serve-vad-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split('?')[0] ?? ''
        if (!url.startsWith('/vad/')) return next()
        const file = join(uiDir, 'public', url)
        if (!existsSync(file)) return next()
        res.setHeader('Content-Type', MIME[extname(file)] ?? 'application/octet-stream')
        createReadStream(file).pipe(res)
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), serveVadAssets()],
})

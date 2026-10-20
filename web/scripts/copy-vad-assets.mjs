/**
 * Copy the Silero VAD model, AudioWorklet and ONNX Runtime WASM binary into
 * `public/vad` so `@ricky0123/vad-web` can run entirely in the browser without
 * fetching from a CDN.
 *
 * These files are generated rather than committed: the packages own them and
 * they are large binaries. `pnpm dev` and `pnpm build` run this script first.
 */
import { copyFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const target = path.join(root, "public", "vad");

const vadPackage = require.resolve("@ricky0123/vad-web/package.json");
const vadDist = path.join(path.dirname(vadPackage), "dist");
const ortEntry = require.resolve("onnxruntime-web/wasm", {
  paths: [path.dirname(vadPackage)],
});
const ortDist = path.dirname(ortEntry);

const files = [
  [path.join(vadDist, "silero_vad_legacy.onnx"), "silero_vad_legacy.onnx"],
  [
    path.join(vadDist, "vad.worklet.bundle.min.js"),
    "vad.worklet.bundle.min.js",
  ],
  // Both halves of the ORT Web WASM loader. The `.mjs` glue is requested by
  // onnxruntime-web 1.30+ and the `.wasm` is the inference binary.
  [
    path.join(ortDist, "ort-wasm-simd-threaded.mjs"),
    "ort-wasm-simd-threaded.mjs",
  ],
  [
    path.join(ortDist, "ort-wasm-simd-threaded.wasm"),
    "ort-wasm-simd-threaded.wasm",
  ],
];

await mkdir(target, { recursive: true });
for (const [source, name] of files) {
  await copyFile(source, path.join(target, name));
}

console.log(
  `Copied ${files.length} VAD assets to ${path.relative(root, target)}`,
);

#!/usr/bin/env node
// =============================================================================
// Build the dashboard: Vite bundles the React app from site/ into dist/, then
// the encrypted payload is copied to dist/data.
//
// The build refuses to run if the payload contains anything that isn't an
// encryption envelope, so plaintext can never be published.
//
//   node tools/build.ts [--data <dir>]   (default: site/data)
// =============================================================================
import type { Dirent } from "node:fs";
import { cp, readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { build } from "vite";

const args = process.argv.slice(2);
const DATA = args[0] === "--data" && args[1] ? args[1] : join("site", "data");
const DST = "dist";

async function assertEncrypted(dir: string): Promise<number> {
  let entries: Dirent[];
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return 0; // no data published yet: the page shows a placeholder
  }
  let count = 0;
  for (const e of entries) {
    const path = join(dir, e.name);
    if (e.isDirectory()) {
      count += await assertEncrypted(path);
      continue;
    }
    const doc = JSON.parse(await readFile(path, "utf8")) as { v?: unknown; iv?: unknown; ct?: unknown; check?: { ct?: unknown } };
    const isEnvelope = typeof doc.iv === "string" && typeof doc.ct === "string" && doc.v === 1;
    const isKeyInfo = e.name === "keyinfo.json" && typeof doc.check?.ct === "string";
    if (!isEnvelope && !isKeyInfo) throw new Error(`refusing to publish non-encrypted file: ${path}`);
    count++;
  }
  return count;
}

const files = await assertEncrypted(DATA);
await build({ configFile: "vite.config.ts", logLevel: "warn" });
if (files) await cp(DATA, join(DST, "data"), { recursive: true });
console.log(`build: dist/ (${files} encrypted data files from ${DATA})`);

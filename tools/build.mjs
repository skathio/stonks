#!/usr/bin/env node
// =============================================================================
// Build the static dashboard: copy site/ to dist/ (the hashira pages-upload
// autodetect target). The payload in site/data is already encrypted, so no
// plaintext ever reaches dist/. The build refuses to run if it finds anything
// that isn't an encryption envelope.
// =============================================================================
import { cp, readdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";

const SRC = "site";
const DST = "dist";

async function assertEncrypted(dir) {
  let entries;
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
    const doc = JSON.parse(await readFile(path, "utf8"));
    const isEnvelope = typeof doc.iv === "string" && typeof doc.ct === "string" && doc.v === 1;
    const isKeyInfo = e.name === "keyinfo.json" && doc.kdf && doc.check;
    if (!isEnvelope && !isKeyInfo) throw new Error(`refusing to publish non-encrypted file: ${path}`);
    count++;
  }
  return count;
}

const files = await assertEncrypted(join(SRC, "data"));
await rm(DST, { recursive: true, force: true });
await cp(SRC, DST, { recursive: true });
console.log(`build: ${SRC}/ -> ${DST}/ (${files} encrypted data files)`);

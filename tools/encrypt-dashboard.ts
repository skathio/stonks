#!/usr/bin/env node
// =============================================================================
// Encrypt the plaintext dashboard payload (private stonks-data/dashboard/)
// into the public site (site/data/). Called by `pipeline publish`.
//
//   STONKS_DASHBOARD_KEY=<43-char base64url> node tools/encrypt-dashboard.ts --src <dir> --dst site/data
//
// Generate a key and its unlock link with tools/new-dashboard-key.ts. The
// destination is rewritten completely each run: nothing stale stays published.
// =============================================================================
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { encryptText, importKeyText, makeKeyInfo } from "../site/src/lib/crypto.ts";

async function listJson(dir: string): Promise<string[]> {
  const out: string[] = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await listJson(path)));
    else if (entry.name.endsWith(".json")) out.push(path);
  }
  return out;
}

export async function encryptDashboard({ src, dst, keyText }: { src: string; dst: string; keyText: string | undefined }): Promise<{ files: number }> {
  const key = await importKeyText(keyText);
  const files = await listJson(src);
  await rm(dst, { recursive: true, force: true });
  await mkdir(dst, { recursive: true });
  for (const file of files) {
    const rel = relative(src, file).split(sep).join("/");
    const envelope = await encryptText(key, await readFile(file, "utf8"), rel);
    await mkdir(dirname(join(dst, rel)), { recursive: true });
    await writeFile(join(dst, rel), JSON.stringify(envelope));
  }
  await writeFile(join(dst, "keyinfo.json"), JSON.stringify(await makeKeyInfo(key), null, 2));
  return { files: files.length };
}

function parseArgs(argv: string[]): { src: string; dst: string } {
  const args: Record<string, string | undefined> = {};
  for (let i = 0; i < argv.length; i += 2) args[(argv[i] ?? "").replace(/^--/, "")] = argv[i + 1];
  const { src, dst } = args;
  if (!src || !dst) throw new Error("usage: encrypt-dashboard.ts --src <dir> --dst <dir>");
  return { src, dst };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    const { src, dst } = parseArgs(process.argv.slice(2));
    const result = await encryptDashboard({ src, dst, keyText: process.env.STONKS_DASHBOARD_KEY });
    console.error(`encrypt-dashboard: ${result.files} files -> ${dst}`);
  } catch (err) {
    console.error(`encrypt-dashboard: ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  }
}

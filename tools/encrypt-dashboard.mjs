#!/usr/bin/env node
// =============================================================================
// Encrypt the plaintext dashboard payload (private stonks-data/dashboard/)
// into the public site (site/data/). Called by `pipeline publish`.
//
//   STONKS_DASHBOARD_PASSPHRASE=... node tools/encrypt-dashboard.mjs --src <dir> --dst site/data
//
// The salt is kept across runs while the passphrase still verifies, so a key
// remembered in the browser keeps working. A new passphrase gets a fresh salt.
// The destination is rewritten completely each run: nothing stale stays published.
// =============================================================================
import { mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import {
  PBKDF2_ITERATIONS, deriveKey, encryptText, makeKeyInfo, randomBytes, toB64, verifyKey,
} from "../site/js/crypto.js";

export const MIN_PASSPHRASE_LENGTH = 20;

async function listJson(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await listJson(path)));
    else if (entry.name.endsWith(".json")) out.push(path);
  }
  return out;
}

async function readExistingKeyInfo(dst) {
  try {
    return JSON.parse(await readFile(join(dst, "keyinfo.json"), "utf8"));
  } catch {
    return null;
  }
}

export async function encryptDashboard({ src, dst, passphrase, iterations = PBKDF2_ITERATIONS }) {
  if (!passphrase || passphrase.length < MIN_PASSPHRASE_LENGTH) {
    throw new Error(`STONKS_DASHBOARD_PASSPHRASE must be at least ${MIN_PASSPHRASE_LENGTH} characters`);
  }
  const previous = await readExistingKeyInfo(dst);
  let salt = toB64(randomBytes(16));
  let key = null;
  if (previous?.kdf?.salt && previous.kdf.iterations === iterations) {
    const candidate = await deriveKey(passphrase, previous.kdf.salt, iterations);
    if (await verifyKey(candidate, previous)) {
      salt = previous.kdf.salt;
      key = candidate;
    }
  }
  key ??= await deriveKey(passphrase, salt, iterations);

  const files = await listJson(src);
  await rm(dst, { recursive: true, force: true });
  await mkdir(dst, { recursive: true });
  for (const file of files) {
    const rel = relative(src, file).split(sep).join("/");
    const envelope = await encryptText(key, await readFile(file, "utf8"), rel);
    await mkdir(dirname(join(dst, rel)), { recursive: true });
    await writeFile(join(dst, rel), JSON.stringify(envelope));
  }
  await writeFile(join(dst, "keyinfo.json"), JSON.stringify(await makeKeyInfo(key, salt, iterations), null, 2));
  return { files: files.length, saltReused: salt === previous?.kdf?.salt };
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, "")] = argv[i + 1];
  if (!args.src || !args.dst) throw new Error("usage: encrypt-dashboard.mjs --src <dir> --dst <dir>");
  return args;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  try {
    const { src, dst } = parseArgs(process.argv.slice(2));
    const result = await encryptDashboard({ src, dst, passphrase: process.env.STONKS_DASHBOARD_PASSPHRASE });
    console.error(`encrypt-dashboard: ${result.files} files -> ${dst} (salt ${result.saltReused ? "reused" : "new"})`);
  } catch (err) {
    console.error(`encrypt-dashboard: ${err.message}`);
    process.exit(1);
  }
}

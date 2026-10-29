import { strict as assert } from "node:assert";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  CHECK_AAD, decryptJson, deriveKey, encryptJson, exportKey, fromB64, importKey, makeKeyInfo, toB64, verifyKey,
} from "../site/js/crypto.js";
import { MIN_PASSPHRASE_LENGTH, encryptDashboard } from "../tools/encrypt-dashboard.mjs";

// Low iteration count keeps the suite fast; the production default is exercised by the constant itself.
const ITER = 1000;
const PASS = "correct horse battery staple 42";
const SALT = toB64(new Uint8Array(16).fill(7));

test("base64 round-trips arbitrary bytes, including large buffers", () => {
  const bytes = new Uint8Array(100_000).map((_, i) => i % 256);
  assert.deepEqual(fromB64(toB64(bytes)), bytes);
});

test("encrypt -> decrypt round-trips JSON", async () => {
  const key = await deriveKey(PASS, SALT, ITER);
  const env = await encryptJson(key, { a: 1, s: "ünïcode" }, "days/2026-10-29.json");
  assert.deepEqual(await decryptJson(key, env, "days/2026-10-29.json"), { a: 1, s: "ünïcode" });
});

test("wrong passphrase fails to decrypt", async () => {
  const key = await deriveKey(PASS, SALT, ITER);
  const wrong = await deriveKey("not the passphrase at all!!", SALT, ITER);
  const env = await encryptJson(key, { secret: true }, "index.json");
  await assert.rejects(decryptJson(wrong, env, "index.json"));
});

test("ciphertext is bound to its path (aad)", async () => {
  const key = await deriveKey(PASS, SALT, ITER);
  const env = await encryptJson(key, { x: 1 }, "days/2026-10-28.json");
  await assert.rejects(decryptJson(key, env, "days/2026-10-29.json"));
});

test("tampered ciphertext is rejected", async () => {
  const key = await deriveKey(PASS, SALT, ITER);
  const env = await encryptJson(key, { x: 1 }, "index.json");
  const ct = fromB64(env.ct);
  ct[0] ^= 1;
  await assert.rejects(decryptJson(key, { ...env, ct: toB64(ct) }, "index.json"));
});

test("unknown envelope versions are rejected", async () => {
  const key = await deriveKey(PASS, SALT, ITER);
  const env = await encryptJson(key, { x: 1 }, "index.json");
  await assert.rejects(decryptJson(key, { ...env, v: 2 }, "index.json"), /unsupported/);
});

test("keyinfo check verifies only the right key; exported keys survive re-import", async () => {
  const key = await deriveKey(PASS, SALT, ITER, true);
  const info = await makeKeyInfo(key, SALT, ITER);
  assert.equal(await verifyKey(key, info), true);
  assert.equal(await verifyKey(await deriveKey("another passphrase entirely", SALT, ITER), info), false);
  const reimported = await importKey(await exportKey(key));
  assert.equal(await verifyKey(reimported, info), true);
  assert.equal(CHECK_AAD, "keyinfo");
});

async function fixture() {
  const root = await mkdtemp(join(tmpdir(), "stonks-enc-"));
  const src = join(root, "dashboard");
  await mkdir(join(src, "days"), { recursive: true });
  await writeFile(join(src, "index.json"), JSON.stringify({ latest: "2026-10-29", days: ["2026-10-29"] }));
  await writeFile(join(src, "days", "2026-10-29.json"), JSON.stringify({ as_of: "2026-10-29" }));
  await writeFile(join(src, "notes.txt"), "ignored: not json");
  return { root, src, dst: join(root, "site-data") };
}

test("encryptDashboard writes envelopes only and keeps the salt while the passphrase verifies", async () => {
  const { root, src, dst } = await fixture();
  try {
    await mkdir(dst, { recursive: true });
    await writeFile(join(dst, "stale.json"), "{}");
    const first = await encryptDashboard({ src, dst, passphrase: PASS, iterations: ITER });
    assert.equal(first.files, 2);
    assert.equal(first.saltReused, false);
    await assert.rejects(readFile(join(dst, "stale.json")), "stale files are removed");

    const info = JSON.parse(await readFile(join(dst, "keyinfo.json"), "utf8"));
    const day = JSON.parse(await readFile(join(dst, "days", "2026-10-29.json"), "utf8"));
    assert.ok(!JSON.stringify(day).includes("2026-10-29"), "plaintext must not leak");
    const key = await deriveKey(PASS, info.kdf.salt, ITER);
    assert.deepEqual(await decryptJson(key, day, "days/2026-10-29.json"), { as_of: "2026-10-29" });

    const second = await encryptDashboard({ src, dst, passphrase: PASS, iterations: ITER });
    assert.equal(second.saltReused, true);
    const rotated = await encryptDashboard({ src, dst, passphrase: `${PASS} rotated`, iterations: ITER });
    assert.equal(rotated.saltReused, false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("encryptDashboard refuses short passphrases", async () => {
  const { root, src, dst } = await fixture();
  try {
    await assert.rejects(
      encryptDashboard({ src, dst, passphrase: "x".repeat(MIN_PASSPHRASE_LENGTH - 1), iterations: ITER }),
      /at least/,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

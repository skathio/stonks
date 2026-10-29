import { strict as assert } from "node:assert";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import {
  CHECK_AAD, decryptJson, encryptJson, extractKeyText, fromB64, fromB64Url, generateKeyText, importKeyText,
  isKeyText, makeKeyInfo, toB64, toB64Url, verifyKey,
} from "../site/src/lib/crypto.js";
import { encryptDashboard } from "../tools/encrypt-dashboard.mjs";

const KEY = generateKeyText();

test("base64 and base64url round-trip arbitrary bytes, including large buffers", () => {
  const bytes = new Uint8Array(100_000).map((_, i) => i % 256);
  assert.deepEqual(fromB64(toB64(bytes)), bytes);
  assert.deepEqual(fromB64Url(toB64Url(bytes)), bytes);
  assert.ok(!/[+/=]/.test(toB64Url(bytes)));
});

test("generated keys are 32-byte base64url and validate", () => {
  assert.equal(KEY.length, 43);
  assert.equal(isKeyText(KEY), true);
  assert.notEqual(generateKeyText(), KEY);
  assert.equal(isKeyText("short"), false);
  assert.equal(isKeyText(`${KEY.slice(0, 42)}!`), false);
  assert.equal(isKeyText(null), false);
});

test("extractKeyText accepts a bare key, an unlock link, or a fragment", () => {
  assert.equal(extractKeyText(KEY), KEY);
  assert.equal(extractKeyText(`https://skathio.github.io/stonks/#k=${KEY}`), KEY);
  assert.equal(extractKeyText(`#k=${KEY}`), KEY);
  assert.equal(extractKeyText(`  ${KEY}\n`), KEY);
  assert.equal(extractKeyText("#/day/2026-10-29"), null);
  assert.equal(extractKeyText(undefined), null);
});

test("importKeyText rejects malformed keys", async () => {
  await assert.rejects(importKeyText("nope"), /base64url/);
});

test("encrypt -> decrypt round-trips JSON", async () => {
  const key = await importKeyText(KEY);
  const env = await encryptJson(key, { a: 1, s: "ünïcode" }, "days/2026-10-29.json");
  assert.deepEqual(await decryptJson(key, env, "days/2026-10-29.json"), { a: 1, s: "ünïcode" });
});

test("wrong key fails to decrypt", async () => {
  const key = await importKeyText(KEY);
  const wrong = await importKeyText(generateKeyText());
  const env = await encryptJson(key, { secret: true }, "index.json");
  await assert.rejects(decryptJson(wrong, env, "index.json"));
});

test("ciphertext is bound to its path (aad)", async () => {
  const key = await importKeyText(KEY);
  const env = await encryptJson(key, { x: 1 }, "days/2026-10-28.json");
  await assert.rejects(decryptJson(key, env, "days/2026-10-29.json"));
});

test("tampered ciphertext and unknown versions are rejected", async () => {
  const key = await importKeyText(KEY);
  const env = await encryptJson(key, { x: 1 }, "index.json");
  const ct = fromB64(env.ct);
  ct[0] ^= 1;
  await assert.rejects(decryptJson(key, { ...env, ct: toB64(ct) }, "index.json"));
  await assert.rejects(decryptJson(key, { ...env, v: 2 }, "index.json"), /unsupported/);
});

test("keyinfo check verifies only the current key", async () => {
  const key = await importKeyText(KEY);
  const info = await makeKeyInfo(key);
  assert.equal(await verifyKey(key, info), true);
  assert.equal(await verifyKey(await importKeyText(generateKeyText()), info), false);
  assert.equal(await verifyKey(key, {}), false);
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

test("encryptDashboard writes envelopes only, removes stale files, never leaks plaintext", async () => {
  const { root, src, dst } = await fixture();
  try {
    await mkdir(dst, { recursive: true });
    await writeFile(join(dst, "stale.json"), "{}");
    const result = await encryptDashboard({ src, dst, keyText: KEY });
    assert.equal(result.files, 2);
    await assert.rejects(readFile(join(dst, "stale.json")), "stale files are removed");
    const day = JSON.parse(await readFile(join(dst, "days", "2026-10-29.json"), "utf8"));
    assert.ok(!JSON.stringify(day).includes("2026-10-29"), "plaintext must not leak");
    const info = JSON.parse(await readFile(join(dst, "keyinfo.json"), "utf8"));
    const key = await importKeyText(KEY);
    assert.equal(await verifyKey(key, info), true);
    assert.deepEqual(await decryptJson(key, day, "days/2026-10-29.json"), { as_of: "2026-10-29" });
    assert.ok(!(await readFile(join(dst, "keyinfo.json"), "utf8")).includes(KEY), "key must not be published");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("encryptDashboard refuses a missing or malformed key", async () => {
  const { root, src, dst } = await fixture();
  try {
    await assert.rejects(encryptDashboard({ src, dst, keyText: undefined }), /base64url/);
    await assert.rejects(encryptDashboard({ src, dst, keyText: "x".repeat(43) + "y" }), /base64url/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

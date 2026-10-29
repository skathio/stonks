// =============================================================================
// Dashboard payload encryption, shared by the browser and tools/encrypt-dashboard.mjs.
//
// Why: the analysis is derived from Massive/Finnhub data whose terms forbid
// public display. GitHub Pages is public, so only ciphertext is published and
// the browser decrypts it locally.
//
// Scheme: a random 256-bit key (STONKS_DASHBOARD_KEY, base64url) and
// AES-256-GCM with a 12-byte random IV per file. The file's path is the
// additional authenticated data, so a ciphertext can't be swapped in under
// another name. The key is high-entropy, so no KDF is needed. It travels in
// the unlock link's #fragment, which browsers never send to the server.
// Uses WebCrypto only (globalThis.crypto.subtle): identical in Node >= 20 and
// in browsers.
// =============================================================================
export const FORMAT_VERSION = 1;
export const KEY_BYTES = 32;
export const CHECK_PLAINTEXT = "stonks-dashboard-ok";
export const CHECK_AAD = "keyinfo";
const KEY_RE = /^[A-Za-z0-9_-]{43}$/;

const subtle = () => globalThis.crypto.subtle;
const enc = new TextEncoder();
const dec = new TextDecoder();

export function toB64(bytes) {
  let bin = "";
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (let i = 0; i < view.length; i += 0x8000) {
    bin += String.fromCharCode(...view.subarray(i, i + 0x8000));
  }
  return btoa(bin);
}

export function fromB64(text) {
  const bin = atob(text);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function toB64Url(bytes) {
  return toB64(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function fromB64Url(text) {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
  return fromB64(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
}

export function randomBytes(n) {
  return globalThis.crypto.getRandomValues(new Uint8Array(n));
}

export function generateKeyText() {
  return toB64Url(randomBytes(KEY_BYTES));
}

export function isKeyText(text) {
  return typeof text === "string" && KEY_RE.test(text) && fromB64Url(text).length === KEY_BYTES;
}

/** Accepts a bare key or anything containing "#k=<key>" (a pasted unlock link). */
export function extractKeyText(input) {
  const text = String(input ?? "").trim();
  const m = text.match(/#k=([A-Za-z0-9_-]{43})/);
  const candidate = m ? m[1] : text;
  return isKeyText(candidate) ? candidate : null;
}

export async function importKeyText(keyText) {
  if (!isKeyText(keyText)) throw new Error("dashboard key must be 32 random bytes, base64url-encoded (43 chars)");
  return subtle().importKey("raw", fromB64Url(keyText), { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
}

export async function encryptText(key, text, aad) {
  const iv = randomBytes(12);
  const ct = await subtle().encrypt({ name: "AES-GCM", iv, additionalData: enc.encode(aad) }, key, enc.encode(text));
  return { v: FORMAT_VERSION, iv: toB64(iv), ct: toB64(ct) };
}

/** Throws (OperationError) on a wrong key, tampered ciphertext or mismatched aad. */
export async function decryptText(key, envelope, aad) {
  if (!envelope || envelope.v !== FORMAT_VERSION) throw new Error("unsupported envelope version");
  const pt = await subtle().decrypt(
    { name: "AES-GCM", iv: fromB64(envelope.iv), additionalData: enc.encode(aad) },
    key,
    fromB64(envelope.ct),
  );
  return dec.decode(pt);
}

export async function encryptJson(key, obj, aad) {
  return encryptText(key, JSON.stringify(obj), aad);
}

export async function decryptJson(key, envelope, aad) {
  return JSON.parse(await decryptText(key, envelope, aad));
}

export async function makeKeyInfo(key) {
  return { v: FORMAT_VERSION, cipher: "AES-256-GCM", check: await encryptText(key, CHECK_PLAINTEXT, CHECK_AAD) };
}

/** True when `key` decrypts the keyinfo check token, i.e. it is the current key. */
export async function verifyKey(key, keyinfo) {
  try {
    return (await decryptText(key, keyinfo.check, CHECK_AAD)) === CHECK_PLAINTEXT;
  } catch {
    return false;
  }
}

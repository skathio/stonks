// =============================================================================
// Dashboard payload encryption, shared by the browser and tools/encrypt-dashboard.mjs.
//
// Why: the analysis is derived from Massive/Finnhub data whose terms forbid
// public display. GitHub Pages is public, so only ciphertext is published and
// the browser decrypts it locally with the passphrase.
//
// Scheme: PBKDF2-SHA256 (600k iterations, 16-byte salt) -> AES-256-GCM with a
// 12-byte random IV per file. The file's path is the additional authenticated
// data, so a ciphertext can't be swapped in under another name.
// Uses WebCrypto only (globalThis.crypto.subtle): identical in Node >= 20 and
// in browsers.
// =============================================================================
export const FORMAT_VERSION = 1;
export const PBKDF2_ITERATIONS = 600_000;
export const CHECK_PLAINTEXT = "stonks-dashboard-ok";
export const CHECK_AAD = "keyinfo";

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

export function randomBytes(n) {
  return globalThis.crypto.getRandomValues(new Uint8Array(n));
}

export async function deriveKey(passphrase, saltB64, iterations = PBKDF2_ITERATIONS, extractable = false) {
  const base = await subtle().importKey("raw", enc.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return subtle().deriveKey(
    { name: "PBKDF2", hash: "SHA-256", salt: fromB64(saltB64), iterations },
    base,
    { name: "AES-GCM", length: 256 },
    extractable,
    ["encrypt", "decrypt"],
  );
}

export async function exportKey(key) {
  return toB64(await subtle().exportKey("raw", key));
}

export async function importKey(rawB64) {
  return subtle().importKey("raw", fromB64(rawB64), { name: "AES-GCM" }, false, ["encrypt", "decrypt"]);
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

export async function makeKeyInfo(key, saltB64, iterations = PBKDF2_ITERATIONS) {
  return {
    v: FORMAT_VERSION,
    kdf: { name: "PBKDF2", hash: "SHA-256", iterations, salt: saltB64 },
    cipher: "AES-256-GCM",
    check: await encryptText(key, CHECK_PLAINTEXT, CHECK_AAD),
  };
}

/** True when `key` decrypts the keyinfo check token, i.e. the passphrase is right. */
export async function verifyKey(key, keyinfo) {
  try {
    return (await decryptText(key, keyinfo.check, CHECK_AAD)) === CHECK_PLAINTEXT;
  } catch {
    return false;
  }
}

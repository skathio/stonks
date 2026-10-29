// =============================================================================
// Key handling + encrypted data loading for the browser.
//
// The key arrives once through the unlock link's #k=<key> fragment (never sent
// to the server), is remembered in localStorage on this device, and is
// stripped from the address bar so it doesn't linger on screen or in history.
// =============================================================================
import { decryptJson, extractKeyText, importKeyText, verifyKey } from "./crypto.js";

const KEY_STORE = "stonks.dashboardKey";

function storage() {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export async function fetchKeyInfo() {
  const res = await fetch("data/keyinfo.json", { cache: "no-cache" });
  if (!res.ok) return null; // nothing published yet
  return res.json();
}

async function tryKey(keyText, keyinfo) {
  if (!keyText) return null;
  try {
    const key = await importKeyText(keyText);
    return (await verifyKey(key, keyinfo)) ? key : null;
  } catch {
    return null;
  }
}

/** Accept a pasted link/key; remembers it on success. Returns a CryptoKey or null. */
export async function acceptKey(input, keyinfo) {
  const keyText = extractKeyText(input);
  const key = await tryKey(keyText, keyinfo);
  if (key) {
    try {
      storage()?.setItem(KEY_STORE, keyText);
    } catch { /* storage blocked: unlock lasts this page view only */ }
  }
  return key;
}

/** Key from the URL fragment (then stripped) or from this device's storage. */
export async function restoreKey(keyinfo) {
  const fromLink = extractKeyText(location.hash);
  if (fromLink) {
    history.replaceState(null, "", `${location.pathname}${location.search}`);
    const key = await acceptKey(fromLink, keyinfo);
    if (key) return key;
  }
  const stored = storage()?.getItem(KEY_STORE);
  if (!stored) return null;
  const key = await tryKey(stored, keyinfo);
  if (!key) storage()?.removeItem(KEY_STORE); // key was rotated
  return key;
}

export function forgetKey() {
  storage()?.removeItem(KEY_STORE);
}

export function hashHasKey() {
  return Boolean(extractKeyText(location.hash));
}

/** Decrypting loader with a per-session cache. */
export function makeLoader(key) {
  const cache = new Map();
  return async function load(rel) {
    if (!cache.has(rel)) {
      cache.set(rel, (async () => {
        const res = await fetch(`data/${rel}`, { cache: "no-cache" });
        if (!res.ok) throw new Error(`${rel}: HTTP ${res.status}`);
        return decryptJson(key, await res.json(), rel);
      })());
    }
    return cache.get(rel);
  };
}

// =============================================================================
// Key handling + encrypted data loading for the browser.
//
// The key arrives once through the unlock link's #k=<key> fragment (never sent
// to the server), is remembered in localStorage on this device, and is
// stripped from the address bar so it doesn't linger on screen or in history.
// =============================================================================
import { decryptJson, extractKeyText, importKeyText, verifyKey } from "./crypto.ts";
import type { Envelope, KeyInfo } from "./types.ts";

const KEY_STORE = "stonks.dashboardKey";

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export async function fetchKeyInfo(): Promise<KeyInfo | null> {
  const res = await fetch("data/keyinfo.json", { cache: "no-cache" });
  if (!res.ok) return null; // nothing published yet
  return (await res.json()) as KeyInfo;
}

async function tryKey(keyText: string | null | undefined, keyinfo: KeyInfo): Promise<CryptoKey | null> {
  if (!keyText) return null;
  try {
    const key = await importKeyText(keyText);
    return (await verifyKey(key, keyinfo)) ? key : null;
  } catch {
    return null;
  }
}

/** Accept a pasted link/key; remembers it on success. Returns a CryptoKey or null. */
export async function acceptKey(input: unknown, keyinfo: KeyInfo): Promise<CryptoKey | null> {
  const keyText = extractKeyText(input);
  const key = await tryKey(keyText, keyinfo);
  if (key) {
    try {
      if (keyText) storage()?.setItem(KEY_STORE, keyText);
    } catch { /* storage blocked: unlock lasts this page view only */ }
  }
  return key;
}

/** Key from the URL fragment (then stripped) or from this device's storage. */
export async function restoreKey(keyinfo: KeyInfo): Promise<CryptoKey | null> {
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

export function forgetKey(): void {
  storage()?.removeItem(KEY_STORE);
}

export function hashHasKey(): boolean {
  return Boolean(extractKeyText(location.hash));
}

/** Decrypting loader with a per-session cache. */
export type Loader = <T>(rel: string) => Promise<T>;

export function makeLoader(key: CryptoKey): Loader {
  const cache = new Map<string, Promise<unknown>>();
  return async function load<T>(rel: string): Promise<T> {
    if (!cache.has(rel)) {
      cache.set(rel, (async () => {
        const res = await fetch(`data/${rel}`, { cache: "no-cache" });
        if (!res.ok) throw new Error(`${rel}: HTTP ${res.status}`);
        return decryptJson(key, (await res.json()) as Envelope, rel);
      })());
    }
    return cache.get(rel) as Promise<T>;
  };
}

import { useSyncExternalStore } from "react";

const STORAGE_KEY = "milpa.session";

export type StoredSession = { token: string; role: string; expiresAt: number };

const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cachedValue: StoredSession | null = null;

function readRaw(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Returns the signed-in session, or null when absent or expired. */
export function getSession(): StoredSession | null {
  const raw = readRaw();
  if (raw === cachedRaw) return cachedValue;
  cachedRaw = raw;
  try {
    const parsed = raw ? (JSON.parse(raw) as StoredSession) : null;
    cachedValue = parsed && parsed.expiresAt > Date.now() ? parsed : null;
  } catch {
    cachedValue = null;
  }
  return cachedValue;
}

export function setSession(session: { token: string; role: string; expiresInSeconds: number } | null): void {
  try {
    if (session) {
      const stored: StoredSession = { token: session.token, role: session.role, expiresAt: Date.now() + session.expiresInSeconds * 1000 };
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage can be blocked; the page keeps working in read-only mode.
  }
  cachedRaw = undefined;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSession(): StoredSession | null {
  return useSyncExternalStore(subscribe, getSession, () => null);
}

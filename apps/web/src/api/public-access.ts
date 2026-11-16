import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, setPublicSessionRenewer } from "./client";
import { apiMode } from "./config";
import { getSession, setSession, useSession } from "./session";

/**
 * The application has no sign-in. It obtains, by itself and silently, the scope-limited public session the
 * server offers for the demo (`POST /v1/auth/demo-session`, enabled with DEMO_PUBLIC_ACCESS=true). The token
 * only lives in sessionStorage, is renewed shortly before it expires and never leaves the browser tab.
 */
let inflight: Promise<boolean> | null = null;

export function acquirePublicSession(force = false): Promise<boolean> {
  if (!force && getSession()) return Promise.resolve(true);
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      if (apiMode === "mock") {
        setSession({ token: "mock-session-token", role: "tecnico", expiresInSeconds: 900, demo: true });
        return true;
      }
      const result = await api.POST("/v1/auth/demo-session");
      if (result.response.ok && result.data) {
        setSession({ token: result.data.access_token, role: result.data.role, expiresInSeconds: result.data.expires_in, demo: true });
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

// A demo token the server no longer accepts (server restarted, key rotated) is replaced once, silently.
setPublicSessionRenewer(() => acquirePublicSession(true));

export type AccessStatus = "ready" | "pending" | "unavailable";

/** Keeps a public session available while `enabled`; re-fetches failed queries once it first arrives. */
export function usePublicAccess(enabled = true): AccessStatus {
  const session = useSession();
  const queryClient = useQueryClient();
  const [failed, setFailed] = useState(false);
  const hasSession = Boolean(session);
  const expiresAt = session?.expiresAt ?? 0;

  useEffect(() => {
    if (!enabled || hasSession) return;
    let cancelled = false;
    void acquirePublicSession().then((ok) => {
      if (cancelled) return;
      setFailed(!ok);
      if (ok) void queryClient.invalidateQueries();
    });
    return () => { cancelled = true; };
  }, [enabled, hasSession, queryClient]);

  useEffect(() => {
    if (!enabled || !hasSession) return;
    const renewIn = Math.max(expiresAt - Date.now() - 60_000, 5_000);
    const handle = window.setTimeout(() => { void acquirePublicSession(true); }, renewIn);
    return () => window.clearTimeout(handle);
  }, [enabled, hasSession, expiresAt]);

  if (hasSession) return "ready";
  return failed ? "unavailable" : "pending";
}

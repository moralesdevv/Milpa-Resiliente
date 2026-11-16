import createClient from "openapi-fetch";

import { apiBaseUrl } from "./config";
import { getSession } from "./session";
import type { paths } from "./types.gen";

export const api = createClient<paths>({ baseUrl: apiBaseUrl });

/**
 * Called when the server rejects a public demo token (for example after the server restarted with a new
 * signing key). It must obtain a fresh public session and resolve to true on success. Registered by
 * `public-access.ts`; kept as a hook so this module does not import it (that would be circular).
 */
let renewPublicSession: (() => Promise<boolean>) | null = null;
export function setPublicSessionRenewer(renewer: (() => Promise<boolean>) | null): void {
  renewPublicSession = renewer;
}

// A request body can only be read once, so a copy is kept to repeat the call after a 401.
const copies = new WeakMap<Request, Request>();

// The bearer token lives only in sessionStorage; it is never written to the URL.
api.use({
  onRequest({ request }) {
    // The call that obtains a public session carries no token: a stale one must not block its renewal.
    if (new URL(request.url, "http://localhost").pathname.endsWith("/v1/auth/demo-session")) return request;
    const session = getSession();
    if (session) request.headers.set("Authorization", `Bearer ${session.token}`);
    if (session?.demo && !request.headers.has("X-Milpa-Retry")) copies.set(request, request.clone());
    return request;
  },
  async onResponse({ request, response }) {
    const copy = copies.get(request);
    copies.delete(request);
    if (response.status !== 401 || !copy || !renewPublicSession) return undefined;
    // Only a demo session is renewed silently; a rejected token that is not a demo token is reported as is.
    if (!(await renewPublicSession())) return undefined;
    const fresh = getSession();
    if (!fresh) return undefined;
    const headers = new Headers(copy.headers);
    headers.set("Authorization", `Bearer ${fresh.token}`);
    headers.set("X-Milpa-Retry", "1");
    return fetch(new Request(copy, { headers }));
  },
});

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly hint?: string;

  constructor(status: number, code: string, message: string, hint?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.hint = hint;
  }
}

export function assertResponse(response: Response, error?: unknown): void {
  if (response.ok) return;

  const payload = typeof error === "object" && error !== null
    ? error as { code?: unknown; detail?: unknown; hint?: unknown }
    : undefined;
  throw new ApiError(
    response.status,
    typeof payload?.code === "string" ? payload.code : `HTTP_${response.status}`,
    typeof payload?.detail === "string" ? payload.detail : "The request could not be completed.",
    typeof payload?.hint === "string" ? payload.hint : undefined,
  );
}

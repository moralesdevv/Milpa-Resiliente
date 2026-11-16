import createClient from "openapi-fetch";

import { apiBaseUrl } from "./config";
import { getSession } from "./session";
import type { paths } from "./types.gen";

export const api = createClient<paths>({ baseUrl: apiBaseUrl });

// The bearer token lives only in sessionStorage; it is never written to the URL.
api.use({
  onRequest({ request }) {
    const session = getSession();
    if (session) request.headers.set("Authorization", `Bearer ${session.token}`);
    return request;
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

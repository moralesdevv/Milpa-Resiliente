import { ApiError } from "./client";
import { apiBaseUrl } from "./config";
import { getSession } from "./session";

export type PdfDownload = {
  filename: string;
  bytes: number;
  /** SHA-256 computed in the browser over the bytes that were actually received. */
  sha256: string | null;
  /** True/false when the browser could compare it with the registered hash; null if it could not. */
  verified: boolean | null;
};

async function sha256Hex(data: ArrayBuffer): Promise<string | null> {
  try {
    if (!globalThis.crypto?.subtle) return null;
    const digest = await globalThis.crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
  } catch {
    return null;
  }
}

/**
 * Downloads the PDF through an authenticated request. A plain link cannot work: the bearer token lives
 * only in sessionStorage and is never put in a URL. The file is saved from a temporary object URL.
 */
export async function downloadReportPdf(reportId: string, pdfUrl: string, expectedSha256: string | null): Promise<PdfDownload> {
  const session = getSession();
  const response = await fetch(`${apiBaseUrl}${pdfUrl}`, {
    headers: session ? { Authorization: `Bearer ${session.token}` } : {},
  });
  if (!response.ok) {
    let code = `HTTP_${response.status}`;
    let message = "The PDF could not be downloaded.";
    try {
      const payload = await response.json() as { code?: unknown; detail?: unknown };
      if (typeof payload.code === "string") code = payload.code;
      if (typeof payload.detail === "string") message = payload.detail;
    } catch { /* the error body is optional */ }
    throw new ApiError(response.status, code, message);
  }
  const buffer = await response.arrayBuffer();
  const sha256 = await sha256Hex(buffer);
  const registered = expectedSha256 ?? response.headers.get("X-Content-SHA256");
  const verified = sha256 && registered ? sha256 === registered.toLowerCase() : null;
  const filename = `milpa-informe-${reportId.slice(0, 8)}.pdf`;
  const url = URL.createObjectURL(new Blob([buffer], { type: "application/pdf" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  return { filename, bytes: buffer.byteLength, sha256, verified };
}

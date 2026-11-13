export const API_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? "/" : "http://localhost:8000");
export const LOCAL_DEMO = import.meta.env.VITE_LOCAL_DEMO === "true" || import.meta.env.VITE_DEMO_LOGIN === "true";
let csrfToken = "";
export function setCsrfToken(value: string) {
  csrfToken = value;
}
export function loginUrl() {
  return `${API_URL.replace(/\/$/, "")}/api/sso/login?return_to=${encodeURIComponent(window.location.pathname)}`;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public correlationId = "",
    public sessionReason = "",
  ) {
    super(message);
  }
}
// No automatic retries: a timed-out mutation may already have committed.
export async function request<T = unknown>(
  path: string,
  method = "GET",
  body?: unknown,
  options: {
    signal?: AbortSignal;
    timeoutMs?: number;
    headers?: Record<string, string>;
    notifyUnauthorized?: boolean;
  } = {},
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort();
  options.signal?.addEventListener("abort", cancel, { once: true });
  if (options.signal?.aborted) controller.abort();
  const timer = setTimeout(
    () => {
      timedOut = true;
      controller.abort();
    },
    options.timeoutMs ?? (method === "GET" ? 20000 : 100000),
  );
  try {
    const response = await fetch(`${API_URL.replace(/\/$/, "")}${path}`, {
      method,
      credentials: "include",
      headers: {
        ...(LOCAL_DEMO && sessionStorage.getItem("governance-token") ? { Authorization: `Bearer ${sessionStorage.getItem("governance-token")}` } : {}),
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        "Content-Type": "application/json",
        ...options.headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const correlation = response.headers.get("x-request-id") || "";
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      throw new ApiError(
        `Server returned an unreadable response (${response.status}). Check operation history before retrying.`,
        response.status,
        correlation,
      );
    }
    if (!response.ok) {
      const sessionReason = ["expired", "ended", "anonymous"].includes(response.headers.get("X-Session-Reason") || "") ? response.headers.get("X-Session-Reason")! : "";
      if (response.status === 401 && options.notifyUnauthorized !== false && !controller.signal.aborted) {
        sessionStorage.removeItem("governance-token");
        window.dispatchEvent(new CustomEvent("governance-session-ended", { detail: { reason: sessionReason } }));
      }
      const detail = payload?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail
                .map(
                  (item: { loc?: string[]; type?: string }) =>
                    `${item.loc?.join(".") || "input"}: ${item.type || "invalid"}`,
                )
                .join("; ")
            : `Request failed (${response.status})`;
      throw new ApiError(message, response.status, correlation, sessionReason);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted)
      throw new Error(
        timedOut
          ? method === "GET"
            ? "Request timed out. Retry loading this page."
            : "Request timed out. Check operation history before retrying."
          : "Request cancelled.",
      );
    throw new Error(
      "Network unavailable. Check your connection and operation history before retrying.",
    );
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", cancel);
  }
}

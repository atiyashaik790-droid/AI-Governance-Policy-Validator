export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export function getToken(): string {
  return sessionStorage.getItem("governance-token") || "";
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public correlationId = "",
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
  } = {},
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort();
  options.signal?.addEventListener("abort", cancel, { once: true });
  if (options.signal?.aborted) controller.abort();
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? 100000);
  try {
    const response = await fetch(`${API_URL.replace(/\/$/, "")}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${getToken()}`,
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
      if (response.status === 401) {
        sessionStorage.removeItem("governance-token");
        window.dispatchEvent(new Event("governance-session-ended"));
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
      throw new ApiError(message, response.status, correlation);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted)
      throw new Error(
        timedOut
          ? "Request timed out. Check operation history before retrying."
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

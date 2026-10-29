export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
// Read the demo credential from session memory; it is never a trusted role selector.
export function getToken(): string {
  return sessionStorage.getItem("governance-token") || "";
}
// Call real backend APIs and preserve meaningful HTTP errors.
export async function request<T = unknown>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${getToken()}`,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok)
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : `Request failed (${response.status})`,
    );
  return payload as T;
}

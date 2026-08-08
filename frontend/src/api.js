const API_BASE = "";

export async function api(path, { method = "GET", body, token, signal, raw } = {}) {
  const headers = {};
  if (body !== undefined && !raw) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    signal,
    body: raw ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = "Request failed";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* ignore */
    }
    const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    // Callers need to tell "your session expired" apart from "the server hiccuped".
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null;
  return res.json();
}

/**
 * Fire-and-forget POST that survives the page being closed mid-flight.
 * Used for impression batches so leaving the tab does not drop the last one.
 */
export function beacon(path, payload, token) {
  const body = JSON.stringify(payload);
  if (!token && navigator.sendBeacon) {
    try {
      navigator.sendBeacon(path, new Blob([body], { type: "application/json" }));
      return;
    } catch {
      /* fall through to fetch */
    }
  }
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  fetch(path, { method: "POST", headers, body, keepalive: true }).catch(() => {});
}

export async function loginRequest(email, password) {
  const form = new URLSearchParams();
  form.set("username", email);
  form.set("password", password);
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) throw new Error("Invalid email or password");
  return res.json();
}

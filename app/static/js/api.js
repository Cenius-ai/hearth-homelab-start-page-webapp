/** Thin JSON client for the Hearth API. */

export class ApiError extends Error {
  constructor(status, body) {
    const message = (body && body.message) || `Request failed (${status})`;
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body || {};
  }

  get fieldErrors() {
    return this.body.errors || {};
  }
}

function parseJson(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function requestJson(path, { method = "GET", body } = {}) {
  const options = {
    method,
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  };
  if (method !== "GET" && method !== "HEAD") {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body ?? {});
  }

  const response = await fetch(path, options);
  const payload = response.status === 204 ? null : parseJson(await response.text());

  if (!response.ok) {
    if (response.status === 401) {
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.assign(`/login?next=${next}`);
    }
    throw new ApiError(response.status, payload);
  }
  return payload;
}

export const api = {
  bootstrap: () => requestJson("/api/bootstrap"),

  login: (email, password) =>
    requestJson("/api/auth/login", { method: "POST", body: { email, password } }),

  register: (email, password, confirmPassword) =>
    requestJson("/api/auth/register", {
      method: "POST",
      body: { email, password, confirm_password: confirmPassword },
    }),

  createService: (payload) =>
    requestJson("/api/services", { method: "POST", body: payload }),

  updateService: (id, payload) =>
    requestJson(`/api/services/${id}`, { method: "PATCH", body: payload }),

  deleteService: (id) => requestJson(`/api/services/${id}`, { method: "DELETE" }),

  checkService: (id) => requestJson(`/api/services/${id}/check`, { method: "POST", body: {} }),

  createBookmark: (payload) =>
    requestJson("/api/bookmarks", { method: "POST", body: payload }),

  deleteBookmark: (id) => requestJson(`/api/bookmarks/${id}`, { method: "DELETE" }),

  saveLayout: (serviceIds) =>
    requestJson("/api/layout", { method: "PUT", body: { service_ids: serviceIds } }),
};

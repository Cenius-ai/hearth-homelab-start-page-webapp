/** Derive the host:port label shown on a tile from the stored service URL. */

export function hostPortFromUrl(url) {
  try {
    const parsed = new URL(url);
    const port = parsed.port || (parsed.protocol === "https:" ? "443" : "80");
    return { host: parsed.hostname, port };
  } catch {
    return { host: "", port: "" };
  }
}

export function formatHostPort(service) {
  if (service.host_port) return service.host_port;
  const { host, port } = hostPortFromUrl(service.url || "");
  return host ? `${host}:${port}` : service.url || "";
}

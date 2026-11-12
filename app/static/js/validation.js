/** Shared client-side shape checks (the server re-validates everything). */

export function isHttpUrl(value) {
  const trimmed = (value || "").trim();
  if (!trimmed || /\s/.test(trimmed)) return false;
  try {
    const parsed = new URL(trimmed);
    return (parsed.protocol === "http:" || parsed.protocol === "https:") && Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

export function isEmail(value) {
  return /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test((value || "").trim());
}

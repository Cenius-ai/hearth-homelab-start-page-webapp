/** Human-facing text for status and timestamps (mirrors app/formatting.py). */

const STATUS_LABELS = { up: "Up", down: "Down" };

export function parseIso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function relativeTime(value) {
  const date = parseIso(value);
  if (!date) return "an unknown time";
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

export function statusLabel(health) {
  if (!health) return "Never checked";
  return STATUS_LABELS[health.status] || "Unknown";
}

export function statusTone(health) {
  if (!health) return "unknown";
  return health.status || "unknown";
}

export function statusDetail(health) {
  if (!health) return "Never checked";
  const label = STATUS_LABELS[health.status] || "Unknown";
  return `${label} — checked ${relativeTime(health.checked_at)}`;
}

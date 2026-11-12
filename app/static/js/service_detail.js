/** Service detail page: destructive-action confirm and on-demand recheck. */

import { api } from "./api.js";
import { statusLabel, statusTone, relativeTime } from "./formatting.js";

const toastEl = document.getElementById("toast");
let toastTimer = null;

function toast(message, kind = "info") {
  if (!toastEl) return;
  toastEl.textContent = message;
  toastEl.classList.toggle("toast--error", kind === "error");
  toastEl.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toastEl.hidden = true;
  }, 4200);
}

document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    const message = form.dataset.confirm || "Are you sure?";
    if (!window.confirm(message)) event.preventDefault();
  });
});

function historyRow(check) {
  const row = document.createElement("tr");

  const statusCell = document.createElement("td");
  statusCell.dataset.label = "Status";
  const dot = document.createElement("span");
  dot.className = `dot dot--${statusTone(check)}`;
  statusCell.append(dot, document.createTextNode(` ${statusLabel(check)}`));

  const latencyCell = document.createElement("td");
  latencyCell.dataset.label = "Latency";
  latencyCell.className = "mono";
  latencyCell.textContent = check.latency_ms === null || check.latency_ms === undefined ? "—" : `${check.latency_ms} ms`;

  const messageCell = document.createElement("td");
  messageCell.dataset.label = "Detail";
  messageCell.textContent = check.message || "—";

  const checkedCell = document.createElement("td");
  checkedCell.dataset.label = "Checked";
  checkedCell.className = "mono";
  checkedCell.textContent = relativeTime(check.checked_at);

  row.append(statusCell, latencyCell, messageCell, checkedCell);
  return row;
}

const recheckButtons = Array.from(document.querySelectorAll("[data-check-service]"));
recheckButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (button.dataset.busy === "1") return;
    const label = button.textContent;
    button.dataset.busy = "1";
    button.disabled = true;
    button.textContent = "Checking…";

    try {
      const payload = await api.checkService(button.dataset.checkService);
      const health = payload.health;

      const statusLine = document.querySelector(".detail__status");
      if (statusLine) {
        statusLine.textContent = `${statusLabel(health)} — checked ${relativeTime(health.checked_at)}`;
      }
      const dot = document.querySelector(".page-head__sub .dot");
      if (dot) dot.className = `dot dot--${statusTone(health)}`;

      const body = document.querySelector(".table--compact tbody");
      if (body) {
        body.insertBefore(historyRow(health), body.firstElementChild);
      } else {
        window.location.reload();
        return;
      }
      toast(`${statusLabel(health)}${health.latency_ms === null ? "" : ` — ${health.latency_ms} ms`}`);
    } catch (error) {
      toast("Couldn't record that check", "error");
    } finally {
      button.disabled = false;
      button.textContent = label;
      delete button.dataset.busy;
    }
  });
});

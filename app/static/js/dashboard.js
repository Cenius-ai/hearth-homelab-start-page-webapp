/** Dashboard entry point: tiles, search, bookmarks, reorder, add-service modal. */

import { api } from "./api.js";
import { initBookmarks } from "./bookmarks.js";
import { initDragAndDrop } from "./dnd.js";
import { initSearch } from "./search.js";
import { initServiceModal } from "./service_form.js";
import { applyHealth, renderGrid } from "./tiles.js";

const toastEl = document.getElementById("toast");
const grid = document.getElementById("tile-grid");
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

const search = initSearch({
  input: document.getElementById("quick-search"),
  emptyState: document.getElementById("search-empty"),
  termTarget: document.getElementById("search-term"),
  clearButtons: [document.getElementById("search-empty-clear")],
});

async function refreshGrid() {
  const payload = await api.bootstrap();
  renderGrid(payload.groups);
  search.refresh();
}

function reorderIds() {
  return Array.from(grid.querySelectorAll(".tile")).map((tile) => Number(tile.dataset.serviceId));
}

if (grid) {
  grid.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-check-service]");
    if (!button) return;
    event.preventDefault();
    if (button.dataset.busy === "1") return;

    const tile = button.closest(".tile");
    button.dataset.busy = "1";
    button.disabled = true;
    const label = button.textContent;
    button.textContent = "Checking…";

    try {
      const payload = await api.checkService(button.dataset.checkService);
      applyHealth(tile, payload.health);
      const detail = payload.health.message ? ` (${payload.health.message})` : "";
      toast(`${payload.health.status === "up" ? "Up" : "Down"}${detail}`);
    } catch (error) {
      toast("Couldn't record that check", "error");
    } finally {
      button.disabled = false;
      button.textContent = label;
      delete button.dataset.busy;
    }
  });

  initDragAndDrop({
    grid,
    onReorder: async () => {
      try {
        await api.saveLayout(reorderIds());
        toast("Tile order saved for your account");
      } catch (error) {
        toast("Couldn't save order — reverted", "error");
        try {
          await refreshGrid();
        } catch (refreshError) {
          toast("Couldn't reload the dashboard", "error");
        }
      }
    },
  });
}

const modal = initServiceModal({
  onSaved: async (service) => {
    try {
      await refreshGrid();
      toast(`${service.name} added to ${service.host_port || "the catalog"}`);
    } catch (error) {
      toast("Service saved — reload to see it", "error");
    }
  },
});

document.querySelectorAll("[data-modal-open]").forEach((trigger) => {
  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    modal.open();
  });
});

initBookmarks({
  onToast: toast,
  onChange: () => search.refresh(),
});

/** Drag-to-reorder within a category group, plus an Alt+Arrow keyboard path. */

export function initDragAndDrop({ grid, onReorder }) {
  if (!grid) return;

  let dragging = null;
  let moved = false;

  grid.addEventListener("dragstart", (event) => {
    const tile = event.target.closest ? event.target.closest(".tile") : null;
    if (!tile) return;
    dragging = tile;
    moved = false;
    tile.classList.add("is-dragging");
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", tile.dataset.serviceId || "");
    }
  });

  grid.addEventListener("dragover", (event) => {
    if (!dragging) return;
    const target = event.target.closest ? event.target.closest(".tile") : null;
    if (!target || target === dragging) return;
    if (target.dataset.categoryId !== dragging.dataset.categoryId) return;
    const list = target.parentElement;
    if (!list) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
    const rect = target.getBoundingClientRect();
    const insertAfter = event.clientY > rect.top + rect.height / 2;
    if (insertAfter) list.insertBefore(dragging, target.nextSibling);
    else list.insertBefore(dragging, target);
    moved = true;
  });

  grid.addEventListener("drop", (event) => {
    if (dragging) event.preventDefault();
  });

  grid.addEventListener("dragend", () => {
    if (!dragging) return;
    dragging.classList.remove("is-dragging");
    const changed = moved;
    dragging = null;
    moved = false;
    if (changed) onReorder();
  });

  grid.addEventListener("keydown", (event) => {
    if (!event.altKey || (event.key !== "ArrowLeft" && event.key !== "ArrowRight")) return;
    const tile = event.target.closest ? event.target.closest(".tile") : null;
    if (!tile) return;
    const list = tile.parentElement;
    if (!list) return;
    event.preventDefault();
    if (event.key === "ArrowLeft") {
      const previous = tile.previousElementSibling;
      if (!previous) return;
      list.insertBefore(tile, previous);
    } else {
      const next = tile.nextElementSibling;
      if (!next) return;
      list.insertBefore(next, tile);
    }
    onReorder();
  });
}

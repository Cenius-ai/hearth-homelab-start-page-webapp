/** Per-user bookmark chips: add, delete, empty state. */

import { api } from "./api.js";
import { isHttpUrl } from "./validation.js";

export function createChip(bookmark) {
  const chip = document.createElement("span");
  chip.className = "chip";
  chip.dataset.bookmarkId = String(bookmark.id);
  chip.dataset.search = `${bookmark.label} ${bookmark.url}`.toLowerCase();

  const link = document.createElement("a");
  link.className = "chip__link";
  link.href = bookmark.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = bookmark.label;

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "chip__remove";
  remove.dataset.bookmarkDelete = String(bookmark.id);
  remove.setAttribute("aria-label", `Remove bookmark ${bookmark.label}`);
  remove.textContent = "×";

  chip.append(link, remove);
  return chip;
}

export function initBookmarks({ onToast, onChange } = {}) {
  const row = document.getElementById("bookmark-row");
  const form = document.getElementById("bookmark-form");
  if (!row || !form) return;

  const toggle = document.getElementById("bookmark-add-toggle");
  const cancel = document.getElementById("bookmark-cancel");
  const emptyNote = document.getElementById("bookmark-empty");
  const errorBox = document.getElementById("bookmark-error");
  const labelInput = document.getElementById("bookmark-label");
  const urlInput = document.getElementById("bookmark-url");
  const submit = document.getElementById("bookmark-submit");

  let busy = false;

  const notify = (message, kind = "info") => {
    if (typeof onToast === "function") onToast(message, kind);
  };

  function updateEmptyState() {
    if (!emptyNote) return;
    const count = row.querySelectorAll(".chip").length;
    emptyNote.hidden = count > 0;
  }

  function showError(message) {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.hidden = !message;
  }

  function openForm() {
    form.hidden = false;
    if (toggle) toggle.setAttribute("aria-expanded", "true");
    showError("");
    if (labelInput) labelInput.focus();
  }

  function closeForm() {
    form.hidden = true;
    if (toggle) toggle.setAttribute("aria-expanded", "false");
    showError("");
  }

  if (toggle) toggle.addEventListener("click", () => (form.hidden ? openForm() : closeForm()));
  if (cancel) cancel.addEventListener("click", closeForm);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;

    const label = labelInput ? labelInput.value.trim() : "";
    const url = urlInput ? urlInput.value.trim() : "";

    if (!label) {
      showError("Please give the bookmark a label.");
      if (labelInput) labelInput.focus();
      return;
    }
    if (!isHttpUrl(url)) {
      showError("URL must start with http:// or https://");
      if (urlInput) urlInput.focus();
      return;
    }

    busy = true;
    if (submit) {
      submit.disabled = true;
      submit.textContent = "Adding…";
    }
    try {
      const payload = await api.createBookmark({ label, url });
      row.append(createChip(payload.bookmark));
      form.reset();
      closeForm();
      updateEmptyState();
      notify(`${label} added to bookmarks`);
      if (typeof onChange === "function") onChange();
    } catch (error) {
      const fieldErrors = error.fieldErrors || {};
      showError(fieldErrors.url || fieldErrors.label || error.message || "Couldn't add that bookmark");
    } finally {
      busy = false;
      if (submit) {
        submit.disabled = false;
        submit.textContent = "Add bookmark";
      }
    }
  });

  row.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-bookmark-delete]");
    if (!button) return;
    event.preventDefault();
    const chip = button.closest(".chip");
    button.disabled = true;
    try {
      await api.deleteBookmark(button.dataset.bookmarkDelete);
      if (chip) chip.remove();
      updateEmptyState();
      notify("Bookmark removed");
      if (typeof onChange === "function") onChange();
    } catch (error) {
      button.disabled = false;
      notify("Couldn't remove that bookmark", "error");
    }
  });

  updateEmptyState();
}

/** The add-service modal. Validation mirrors the server rules. */

import { api } from "./api.js";
import { isHttpUrl } from "./validation.js";

export function initServiceModal({ onSaved } = {}) {
  const dialog = document.getElementById("service-modal");
  const form = document.getElementById("service-form");
  if (!dialog || !form) return { open() {} };

  const fields = {
    name: document.getElementById("service-name"),
    url: document.getElementById("service-url"),
    category_id: document.getElementById("service-category"),
    icon: document.getElementById("service-icon"),
  };
  const formError = document.getElementById("service-form-error");
  const submit = document.getElementById("service-submit");
  const closeButton = document.getElementById("service-modal-close");
  const cancelButton = document.getElementById("service-cancel");
  let busy = false;

  function errorSlot(field) {
    return document.querySelector(`#service-form [data-error-for="${field}"]`);
  }

  function clearErrors() {
    form.querySelectorAll("[data-error-for]").forEach((slot) => {
      slot.textContent = "";
      slot.hidden = true;
    });
    form.querySelectorAll("[aria-invalid]").forEach((input) => input.removeAttribute("aria-invalid"));
    if (formError) {
      formError.textContent = "";
      formError.hidden = true;
    }
  }

  function showErrors(errors) {
    clearErrors();
    let firstField = null;
    Object.entries(errors).forEach(([field, message]) => {
      const slot = errorSlot(field);
      if (slot) {
        slot.textContent = message;
        slot.hidden = false;
      } else if (formError) {
        formError.textContent = message;
        formError.hidden = false;
      }
      const input = fields[field];
      if (input) {
        input.setAttribute("aria-invalid", "true");
        if (!firstField) firstField = input;
      }
    });
    if (firstField) firstField.focus();
  }

  function setBusy(next) {
    busy = next;
    if (submit) {
      submit.disabled = next;
      submit.textContent = next ? "Adding…" : "Add service";
    }
  }

  function open() {
    clearErrors();
    form.reset();
    dialog.showModal();
    if (fields.name) fields.name.focus();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;

    const values = {
      name: fields.name ? fields.name.value.trim() : "",
      url: fields.url ? fields.url.value.trim() : "",
      category_id: fields.category_id ? fields.category_id.value : "",
      icon: fields.icon ? fields.icon.value.trim() : "",
    };

    const errors = {};
    if (!values.name) errors.name = "Please give the service a name.";
    if (!values.url) errors.url = "Please enter a URL.";
    else if (!isHttpUrl(values.url)) errors.url = "URL must start with http:// or https://";
    if (!values.category_id) errors.category_id = "Please choose a category.";

    if (Object.keys(errors).length > 0) {
      showErrors(errors);
      return;
    }

    setBusy(true);
    try {
      const payload = await api.createService(values);
      dialog.close();
      form.reset();
      if (typeof onSaved === "function") onSaved(payload.service);
    } catch (error) {
      const fieldErrors = error.fieldErrors || {};
      showErrors(Object.keys(fieldErrors).length ? fieldErrors : { _: error.message });
    } finally {
      setBusy(false);
    }
  });

  if (closeButton) closeButton.addEventListener("click", () => dialog.close());
  if (cancelButton) cancelButton.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", clearErrors);

  return { open };
}

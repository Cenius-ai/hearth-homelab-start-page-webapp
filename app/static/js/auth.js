/** Login and registration forms. */

import { api } from "./api.js";
import { isEmail } from "./validation.js";

function errorSlot(field) {
  return document.querySelector(`[data-error-for="${field}"]`);
}

function clearErrors(form) {
  form.querySelectorAll("[data-error-for]").forEach((slot) => {
    slot.textContent = "";
    slot.hidden = true;
  });
  form.querySelectorAll("[aria-invalid]").forEach((input) => input.removeAttribute("aria-invalid"));
  const formError = document.getElementById("form-error");
  if (formError) {
    formError.textContent = "";
    formError.hidden = true;
  }
}

function showErrors(form, errors) {
  clearErrors(form);
  let firstInput = null;
  Object.entries(errors).forEach(([field, message]) => {
    const slot = errorSlot(field);
    if (slot) {
      slot.textContent = message;
      slot.hidden = false;
    } else {
      const formError = document.getElementById("form-error");
      if (formError) {
        formError.textContent = message;
        formError.hidden = false;
      }
    }
    const input = form.querySelector(`[name="${field}"]`);
    if (input) {
      input.setAttribute("aria-invalid", "true");
      if (!firstInput) firstInput = input;
    }
  });
  if (firstInput) firstInput.focus();
}

function setBusy(button, busy, idleLabel, busyLabel) {
  if (!button) return;
  button.disabled = busy;
  button.textContent = busy ? busyLabel : idleLabel;
}

function safeNext(value) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

function setupPasswordToggle() {
  const toggle = document.getElementById("password-toggle");
  if (!toggle) return;
  const targets = [document.getElementById("password"), document.getElementById("confirm_password")].filter(
    Boolean,
  );
  toggle.addEventListener("click", () => {
    const showing = toggle.getAttribute("aria-pressed") === "true";
    targets.forEach((input) => {
      input.type = showing ? "password" : "text";
    });
    toggle.setAttribute("aria-pressed", showing ? "false" : "true");
    toggle.textContent = showing ? "Show" : "Hide";
    toggle.setAttribute("aria-label", showing ? "Show password" : "Hide password");
  });
}

function setupLogin() {
  const form = document.getElementById("login-form");
  if (!form) return;
  const submit = document.getElementById("login-submit");
  const email = form.querySelector("#email");
  const password = form.querySelector("#password");
  let busy = false;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;

    const errors = {};
    if (!email.value.trim()) errors.email = "Please enter your email address.";
    else if (!isEmail(email.value)) errors.email = "Please enter a valid email address.";
    if (!password.value) errors.password = "Please enter your password.";
    if (Object.keys(errors).length > 0) {
      showErrors(form, errors);
      return;
    }

    busy = true;
    setBusy(submit, true, "Sign in", "Signing in…");
    clearErrors(form);
    try {
      await api.login(email.value.trim(), password.value);
      window.location.assign(safeNext(form.dataset.next));
    } catch (error) {
      const fieldErrors = error.fieldErrors || {};
      if (Object.keys(fieldErrors).length > 0) {
        showErrors(form, fieldErrors);
      } else {
        showErrors(form, { _: error.message || "Email or password is incorrect" });
      }
      busy = false;
      setBusy(submit, false, "Sign in", "Signing in…");
    }
  });
}

function setupRegister() {
  const form = document.getElementById("register-form");
  if (!form) return;
  const submit = document.getElementById("register-submit");
  const email = form.querySelector("#email");
  const password = form.querySelector("#password");
  const confirm = form.querySelector("#confirm_password");
  let busy = false;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;

    const errors = {};
    if (!email.value.trim()) errors.email = "Please enter your email address.";
    else if (!isEmail(email.value)) errors.email = "Please enter a valid email address.";
    if (!password.value) errors.password = "Please enter a password.";
    else if (password.value.length < 8) errors.password = "Password must be at least 8 characters.";
    if (!confirm.value) errors.confirm_password = "Please confirm your password.";
    else if (confirm.value !== password.value) errors.confirm_password = "Passwords do not match.";

    if (Object.keys(errors).length > 0) {
      showErrors(form, errors);
      return;
    }

    busy = true;
    setBusy(submit, true, "Create account", "Creating account…");
    clearErrors(form);
    try {
      await api.register(email.value.trim(), password.value, confirm.value);
      window.location.assign("/");
    } catch (error) {
      const fieldErrors = error.fieldErrors || {};
      showErrors(form, Object.keys(fieldErrors).length ? fieldErrors : { _: error.message });
      busy = false;
      setBusy(submit, false, "Create account", "Creating account…");
    }
  });
}

setupPasswordToggle();
setupLogin();
setupRegister();

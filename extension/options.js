// Options page. Reads/writes the settings through chrome.storage.sync, reusing
// the pure validation in lib/settings.js. chrome + document are only touched
// here; lib/ stays free of browser dependencies.

import {
  DEFAULT_SETTINGS,
  SETTINGS_STORAGE_KEY,
  validateSettings,
} from "./lib/settings.js";
import { STORES, STORE_KEYS } from "./lib/stores.js";

const $ = (sel) => document.querySelector(sel);

const form = $("#options-form");
const statusEl = $("#save-status");
const resetBtn = $("#reset");

function showStatus(kind, message) {
  statusEl.className = `status ${kind}`;
  statusEl.textContent = message;
  statusEl.classList.remove("hidden");
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function buildStoreToggles() {
  const container = $("#stores");
  for (const key of STORE_KEYS) {
    const label = document.createElement("label");
    label.className = "store-toggle";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = "store";
    checkbox.value = key;
    checkbox.dataset.store = key;

    const text = document.createElement("span");
    text.textContent = STORES[key].label;

    label.append(checkbox, text);
    container.append(label);
  }
}

function populateForm(settings) {
  form.elements.apiUrl.value = settings.apiUrl;
  form.elements.frontendUrl.value = settings.frontendUrl;
  form.elements.syncIntervalHours.value = String(settings.syncIntervalHours);
  form.elements.cooldownMinutes.value = String(settings.cooldownMinutes);
  for (const key of STORE_KEYS) {
    const checkbox = form.querySelector(`input[data-store="${key}"]`);
    if (checkbox) checkbox.checked = settings.stores[key].enabled;
  }
}

function readForm() {
  const stores = {};
  for (const key of STORE_KEYS) {
    const checkbox = form.querySelector(`input[data-store="${key}"]`);
    stores[key] = { enabled: checkbox ? checkbox.checked : true };
  }
  return {
    apiUrl: form.elements.apiUrl.value.trim(),
    frontendUrl: form.elements.frontendUrl.value.trim(),
    syncIntervalHours: Number(form.elements.syncIntervalHours.value),
    cooldownMinutes: Number(form.elements.cooldownMinutes.value),
    stores,
  };
}

async function loadSettings() {
  const stored = await chrome.storage.sync.get([SETTINGS_STORAGE_KEY]);
  const { settings } = validateSettings(stored[SETTINGS_STORAGE_KEY]);
  populateForm(settings);
}

async function saveSettings(event) {
  event.preventDefault();
  hideStatus();

  const { valid, errors, settings } = validateSettings(readForm());
  if (!valid) {
    showStatus("error", `Réglages non enregistrés : ${errors.join(" · ")}`);
    return;
  }

  try {
    await chrome.storage.sync.set({ [SETTINGS_STORAGE_KEY]: settings });
    showStatus("success", "Réglages enregistrés.");
  } catch (err) {
    showStatus("error", `Échec de l'enregistrement : ${err?.message ?? err}`);
  }
}

async function resetSettings() {
  hideStatus();
  populateForm(DEFAULT_SETTINGS);
  try {
    await chrome.storage.sync.set({ [SETTINGS_STORAGE_KEY]: DEFAULT_SETTINGS });
    showStatus("success", "Réglages réinitialisés aux valeurs par défaut.");
  } catch (err) {
    showStatus("error", `Échec de la réinitialisation : ${err?.message ?? err}`);
  }
}

function bindEvents() {
  form.addEventListener("submit", saveSettings);
  resetBtn.addEventListener("click", () => void resetSettings());
}

async function init() {
  buildStoreToggles();
  bindEvents();
  try {
    await loadSettings();
  } catch (err) {
    console.warn("[AdamHUB] loadSettings failed:", err);
    populateForm(DEFAULT_SETTINGS);
    showStatus("error", "Impossible de charger les réglages.");
  }
}

init();

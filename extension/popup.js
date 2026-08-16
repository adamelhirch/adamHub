// Popup UI. Thin layer over lib/: auth resolution, settings loading, per-store
// status rendering and the global "Synchroniser maintenant" button. All sync
// decisions and the import flow live in lib/sync.js — the same path the
// background worker uses.

import { createAuth } from "./lib/auth.js";
import { createSync } from "./lib/sync.js";
import { STORE_KEYS } from "./lib/stores.js";
import {
  validateSettings,
  matchesFrontend,
  SETTINGS_STORAGE_KEY,
} from "./lib/settings.js";

const $ = (sel) => document.querySelector(sel);
const statusEl = $("#status");
const authPrompt = $("#auth-prompt");
const accountBadge = $("#account-badge");
const syncPanel = $("#sync-panel");
const syncNowBtn = $("#sync-now");
const openHubBtn = $("#open-hub");

let auth;
let sync;
let apiUrl;
let frontendUrl;
let lastSync = {};

function showStatus(kind, message) {
  statusEl.className = `status ${kind}`;
  statusEl.textContent = message;
  statusEl.classList.remove("hidden");
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function showAuthPrompt(show) {
  authPrompt.classList.toggle("hidden", !show);
}

function formatStamp(stamp) {
  const date = new Date(stamp);
  return `synchronisé le ${date.toLocaleDateString("fr-FR")} à ${date.toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

async function loadSettings() {
  try {
    const stored = await chrome.storage.sync.get([SETTINGS_STORAGE_KEY]);
    return validateSettings(stored[SETTINGS_STORAGE_KEY]).settings;
  } catch (err) {
    console.warn("[AdamHUB] loadSettings failed:", err);
    return validateSettings(undefined).settings;
  }
}

async function findHubTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs.filter((tab) => tab && matchesFrontend(tab.url, frontendUrl));
}

async function resolveToken() {
  // Cached token first, then scan open AdamHUB tabs for a fresh JWT.
  let token = await auth.getToken();
  if (token) return token;
  for (const tab of await findHubTabs()) {
    const read = await auth.readTokenFromTab(tab.id);
    if (read) {
      await auth.setToken(read);
      return read;
    }
  }
  return null;
}

async function fetchAccount(token) {
  try {
    const response = await fetch(`${apiUrl}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

async function refreshAccountBadge() {
  const token = await resolveToken();
  if (!token) {
    accountBadge.classList.add("hidden");
    syncPanel.classList.add("hidden");
    showAuthPrompt(true);
    return false;
  }
  const account = await fetchAccount(token);
  if (!account) {
    accountBadge.classList.add("hidden");
    syncPanel.classList.add("hidden");
    showAuthPrompt(true);
    await auth.clearToken();
    return false;
  }
  accountBadge.textContent = account.display_name;
  accountBadge.classList.remove("hidden");
  syncPanel.classList.remove("hidden");
  showAuthPrompt(false);
  return true;
}

function renderStoreMeta(key, error = null) {
  const meta = document.getElementById(`meta-${key}`);
  if (!meta) return;
  meta.classList.remove("connected", "error");
  if (error) {
    meta.textContent = `échec : ${error}`;
    meta.classList.add("error");
    return;
  }
  const stamp = lastSync[key];
  if (stamp) {
    meta.textContent = formatStamp(stamp);
    meta.classList.add("connected");
  } else {
    meta.textContent = "non connecté";
  }
}

async function refreshConnectionStatus() {
  const stored = await chrome.storage.local.get(["lastSync"]);
  lastSync = stored.lastSync || {};
  for (const key of STORE_KEYS) {
    renderStoreMeta(key);
  }
}

async function runSyncNow() {
  hideStatus();
  syncNowBtn.disabled = true;
  syncNowBtn.textContent = "Synchronisation…";
  try {
    const token = await resolveToken();
    if (!token) {
      showAuthPrompt(true);
      showStatus("info", "Ouvre AdamHUB dans un onglet et connecte-toi pour démarrer.");
      return;
    }

    const results = await sync.syncAll(token);

    // Re-read lastSync (updated by lib/sync) then render per-store status.
    const stored = await chrome.storage.local.get(["lastSync"]);
    lastSync = stored.lastSync || {};

    const failures = [];
    for (const r of results) {
      if (r.ok) {
        renderStoreMeta(r.storeKey);
      } else {
        renderStoreMeta(r.storeKey, r.error);
        failures.push(r);
      }
    }

    if (results.some((r) => r.unauthorized)) {
      showStatus("error", "Session expirée. Reconnecte-toi sur AdamHUB puis recommence.");
      await refreshAccountBadge();
    } else if (failures.length === 0) {
      showStatus("success", `✓ ${results.length} enseigne(s) synchronisée(s).`);
    } else {
      showStatus("error", `✗ ${failures.length}/${results.length} enseigne(s) en échec.`);
    }
  } catch (err) {
    showStatus("error", `✗ ${err.message ?? err}`);
  } finally {
    syncNowBtn.disabled = false;
    syncNowBtn.textContent = "Synchroniser maintenant";
  }
}

function bindEventListeners() {
  openHubBtn.addEventListener("click", async () => {
    try {
      await chrome.tabs.create({ url: frontendUrl });
    } catch (err) {
      showStatus("error", `Impossible d'ouvrir AdamHUB : ${err.message ?? err}`);
    }
  });
  syncNowBtn.addEventListener("click", () => {
    void runSyncNow();
  });
}

async function init() {
  bindEventListeners();

  const settings = await loadSettings();
  apiUrl = settings.apiUrl;
  frontendUrl = settings.frontendUrl;

  auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });
  sync = createSync({
    storage: chrome.storage.local,
    cookies: chrome.cookies,
    fetchFn: fetch,
    apiUrl,
  });

  let ok = false;
  try {
    ok = await refreshAccountBadge();
  } catch (err) {
    console.warn("[AdamHUB] init refreshAccountBadge:", err);
  }
  try {
    await refreshConnectionStatus();
  } catch (err) {
    console.warn("[AdamHUB] init refreshConnectionStatus:", err);
  }
  if (!ok) {
    showStatus("info", "Ouvre AdamHUB dans un onglet et connecte-toi pour démarrer.");
  }
}

init();

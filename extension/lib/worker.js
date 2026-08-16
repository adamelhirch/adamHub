// Background service-worker logic, extracted from background.js so it can be
// unit-tested without a browser. Everything chrome- or time-dependent is
// injected by the caller; background.js is the thin wiring that passes the
// live globals.

import { STORES, STORE_KEYS, getStore } from "./stores.js";
import { createAuth } from "./auth.js";
import { validateSettings, SETTINGS_STORAGE_KEY } from "./settings.js";
import { normalizeCookie, buildPayload, shouldSync } from "./sync.js";

export const ALARM_NAME = "adamhub-sync";
export const LAST_SYNC_KEY = "lastSync";
export const IMPORT_PATH = "/api/v1/supermarket/connections/import";

/**
 * Map a tab URL to its store key (or null when the URL is not a store domain).
 * Pure — no chrome dependency.
 *
 * @param {string|null|undefined} url
 * @returns {string|null}
 */
export function matchStoreByUrl(url) {
  if (!url) return null;
  let host;
  try {
    host = new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
  for (const key of STORE_KEYS) {
    const def = STORES[key];
    for (const domain of def.cookieDomains) {
      const bare = domain.startsWith(".") ? domain.slice(1) : domain;
      const bareLower = bare.toLowerCase();
      if (host === bareLower || host.endsWith("." + bareLower)) {
        return key;
      }
    }
  }
  return null;
}

/**
 * Build the background worker on top of the injected chrome + fetch + clock.
 *
 * @param {object} deps
 * @param {object} deps.chrome  The full chrome API surface.
 * @param {typeof fetch} [deps.fetchFn]  Injectable fetch for tests.
 * @param {() => number} [deps.now]  Injectable clock for tests.
 */
export function createWorker({ chrome, fetchFn = globalThis.fetch, now = () => Date.now() }) {
  const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });
  const openHubNotifications = new Set();
  let notificationSeq = 0;

  async function loadSettings() {
    const data = await chrome.storage.sync.get([SETTINGS_STORAGE_KEY]);
    const { settings } = validateSettings(data[SETTINGS_STORAGE_KEY]);
    return settings;
  }

  async function readLastSync() {
    const data = await chrome.storage.local.get([LAST_SYNC_KEY]);
    return data[LAST_SYNC_KEY] ?? {};
  }

  async function updateLastSync(storeKey, timestamp) {
    const lastSync = await readLastSync();
    lastSync[storeKey] = timestamp;
    await chrome.storage.local.set({ [LAST_SYNC_KEY]: lastSync });
  }

  async function notify(message, { openHub = false } = {}) {
    const id = `adamhub-${now()}-${notificationSeq++}`;
    if (openHub) openHubNotifications.add(id);
    const iconUrl =
      typeof chrome.runtime?.getURL === "function"
        ? chrome.runtime.getURL("icon128.png")
        : "icon128.png";
    await chrome.notifications.create(id, {
      type: "basic",
      iconUrl,
      title: "AdamHUB Connect",
      message,
    });
    return id;
  }

  async function openHub() {
    const settings = await loadSettings();
    await chrome.tabs.create({ url: settings.frontendUrl });
  }

  async function scheduleAlarm() {
    const settings = await loadSettings();
    const periodMinutes = Math.max(1, Math.round(settings.syncIntervalHours * 60));
    await chrome.alarms.create(ALARM_NAME, { periodInMinutes: periodMinutes });
    return periodMinutes;
  }

  async function readCookiesForStore(storeKey) {
    const def = getStore(storeKey);
    const cookies = [];
    const seen = new Set();
    for (const domain of def.cookieDomains) {
      const list = await chrome.cookies.getAll({ domain });
      for (const cookie of list) {
        const fp = `${cookie.name}|${cookie.domain}|${cookie.path}`;
        if (seen.has(fp)) continue;
        seen.add(fp);
        cookies.push(normalizeCookie(cookie));
      }
    }
    return cookies;
  }

  async function readErrorDetail(response) {
    try {
      const data = await response.json();
      return data.detail ?? JSON.stringify(data);
    } catch {
      try {
        return await response.text();
      } catch {
        return "";
      }
    }
  }

  /**
   * Run the sync flow for a single store. Returns a short status string so the
   * caller (and tests) can tell why a sync did or did not happen.
   */
  async function syncStore(storeKey, settings) {
    const def = getStore(storeKey);
    if (!def) return "unknown-store";

    if (!(settings.stores[storeKey]?.enabled ?? true)) return "disabled";

    const lastSync = (await readLastSync())[storeKey] ?? null;
    if (!shouldSync({ lastSync, cooldownMinutes: settings.cooldownMinutes, now: now() })) {
      return "cooldown";
    }

    const token = await auth.getToken();
    if (!token) return "no-token";

    const cookies = await readCookiesForStore(storeKey);
    if (cookies.length === 0) return "no-cookies";
    if (def.sessionMarker && !cookies.some((c) => c.name === def.sessionMarker)) {
      return "no-session";
    }

    const payload = buildPayload({ storeKey, cookies });
    let response;
    try {
      response = await fetchFn(`${settings.apiUrl}${IMPORT_PATH}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      await notify(`Erreur de synchro ${def.label} : ${err?.message ?? err}.`);
      return "network-error";
    }

    if (response.status === 401) {
      await auth.clearToken();
      await notify("Session AdamHUB expirée — reconnecte-toi pour reprendre la synchro.", {
        openHub: true,
      });
      return "unauthorized";
    }

    if (!response.ok) {
      const detail = await readErrorDetail(response);
      const suffix = detail ? ` — ${detail}` : "";
      await notify(`Échec de la synchro ${def.label} (HTTP ${response.status}${suffix}).`);
      return "http-error";
    }

    await updateLastSync(storeKey, now());
    return "synced";
  }

  async function syncAll() {
    const settings = await loadSettings();
    const results = {};
    for (const key of STORE_KEYS) {
      results[key] = await syncStore(key, settings);
    }
    return results;
  }

  async function handleInstalled(details) {
    await scheduleAlarm();
    if (details?.reason !== "install") return "scheduled";
    const token = await auth.getToken();
    if (!token) {
      await notify("Reconnecte-toi sur AdamHUB pour activer la synchronisation automatique.", {
        openHub: true,
      });
      return "reconnect";
    }
    return syncAll();
  }

  async function handleStartup() {
    await scheduleAlarm();
  }

  async function handleAlarm(alarm) {
    if (!alarm || alarm.name !== ALARM_NAME) return null;
    return syncAll();
  }

  async function handleTabUpdated(_tabId, changeInfo, tab) {
    if (changeInfo?.status !== "complete") return null;
    const storeKey = matchStoreByUrl(tab?.url);
    if (!storeKey) return null;
    const settings = await loadSettings();
    return syncStore(storeKey, settings);
  }

  async function handleNotificationClicked(id) {
    if (openHubNotifications.has(id)) {
      openHubNotifications.delete(id);
      await openHub();
    }
  }

  return {
    handleInstalled,
    handleStartup,
    handleAlarm,
    handleTabUpdated,
    handleNotificationClicked,
    syncAll,
    syncStore,
    scheduleAlarm,
    loadSettings,
    readLastSync,
    updateLastSync,
    notify,
    openHub,
    readCookiesForStore,
  };
}

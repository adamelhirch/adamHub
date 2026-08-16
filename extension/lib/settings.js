// Settings schema, defaults and validation. Pure — no chrome dependency. The
// defaults mirror the values that used to be hard-coded in popup.js so an
// options page can be added without changing behaviour for existing users.

import { STORE_KEYS } from "./stores.js";

/**
 * The chrome.storage.sync key under which the options page persists the user's
 * settings and the background worker reads them back. Defined here so both
 * surfaces share a single source of truth.
 */
export const SETTINGS_STORAGE_KEY = "settings";

const URL_RE = /^https?:\/\/.+/;

const LOOPBACK_ALIASES = {
  "127.0.0.1": "localhost",
  localhost: "127.0.0.1",
};

/** chrome.storage.sync key the options page reads/writes the settings under. */
export const SETTINGS_STORAGE_KEY = "settings";

function defaultStoreToggles() {
  return Object.fromEntries(STORE_KEYS.map((key) => [key, { enabled: true }]));
}

/**
 * The canonical settings shape and its current defaults. This is the single
 * source of truth the options page reads from and writes back to.
 */
export const DEFAULT_SETTINGS = Object.freeze({
  apiUrl: "http://127.0.0.1:8000",
  frontendUrl: "http://localhost:5173",
  syncIntervalHours: 6,
  cooldownMinutes: 30,
  stores: Object.freeze(defaultStoreToggles()),
});

/**
 * Validate and normalize a (possibly partial, possibly malformed) settings
 * object into a full, usable settings object. Invalid fields fall back to
 * their default and are reported in `errors`; never throws.
 *
 * @param {object} [input]
 * @returns {{ valid: boolean, errors: string[], settings: object }}
 */
export function validateSettings(input = {}) {
  const errors = [];
  const src = input ?? {};

  let apiUrl = DEFAULT_SETTINGS.apiUrl;
  if (typeof src.apiUrl === "string" && URL_RE.test(src.apiUrl)) {
    apiUrl = src.apiUrl;
  } else if (src.apiUrl !== undefined) {
    errors.push("apiUrl invalide");
  }

  let frontendUrl = DEFAULT_SETTINGS.frontendUrl;
  if (typeof src.frontendUrl === "string" && URL_RE.test(src.frontendUrl)) {
    frontendUrl = src.frontendUrl;
  } else if (src.frontendUrl !== undefined) {
    errors.push("frontendUrl invalide");
  }

  let syncIntervalHours = DEFAULT_SETTINGS.syncIntervalHours;
  if (
    typeof src.syncIntervalHours === "number" &&
    Number.isFinite(src.syncIntervalHours) &&
    src.syncIntervalHours > 0
  ) {
    syncIntervalHours = src.syncIntervalHours;
  } else if (src.syncIntervalHours !== undefined) {
    errors.push("syncIntervalHours invalide");
  }

  let cooldownMinutes = DEFAULT_SETTINGS.cooldownMinutes;
  if (
    typeof src.cooldownMinutes === "number" &&
    Number.isFinite(src.cooldownMinutes) &&
    src.cooldownMinutes >= 0
  ) {
    cooldownMinutes = src.cooldownMinutes;
  } else if (src.cooldownMinutes !== undefined) {
    errors.push("cooldownMinutes invalide");
  }

  const stores = {};
  for (const key of STORE_KEYS) {
    const enabled =
      src.stores && src.stores[key] && typeof src.stores[key].enabled === "boolean"
        ? src.stores[key].enabled
        : true;
    stores[key] = { enabled };
  }

  return {
    valid: errors.length === 0,
    errors,
    settings: { apiUrl, frontendUrl, syncIntervalHours, cooldownMinutes, stores },
  };
}

/**
 * Derive the base origins that identify "the frontend" from its configured
 * URL. For loopback hosts both spellings are returned (localhost and
 * 127.0.0.1) so a tab opened on either host matches a config pointing at the
 * other. Used both to open the hub and to match open AdamHUB tabs.
 *
 * @param {string} frontendUrl
 * @returns {string[]} normalized origins (scheme://host[:port])
 */
export function frontendOrigins(frontendUrl) {
  let parsed;
  try {
    parsed = new URL(frontendUrl);
  } catch {
    return [];
  }
  const origins = [parsed.origin];
  const alias = LOOPBACK_ALIASES[parsed.hostname];
  if (alias) {
    parsed.hostname = alias;
    origins.push(parsed.origin);
  }
  return origins;
}

/**
 * Whether a tab URL points at the configured frontend. Loopback-host tolerant
 * (localhost ↔ 127.0.0.1) and path-insensitive: origin comparison only.
 *
 * @param {string|null|undefined} tabUrl
 * @param {string} frontendUrl
 * @returns {boolean}
 */
export function matchesFrontend(tabUrl, frontendUrl) {
  if (typeof tabUrl !== "string" || tabUrl === "") return false;
  let tab;
  try {
    tab = new URL(tabUrl);
  } catch {
    return false;
  }
  return frontendOrigins(frontendUrl).includes(tab.origin);
}

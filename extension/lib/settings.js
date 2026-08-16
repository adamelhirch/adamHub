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
const PORT_RE = /^\d+$/;

function isValidPort(value) {
  return (
    (typeof value === "number" && Number.isInteger(value)) ||
    (typeof value === "string" && PORT_RE.test(value))
  );
}

function toPort(value) {
  const port = typeof value === "string" ? Number(value) : value;
  return Number.isInteger(port) && port >= 1 && port <= 65535 ? port : null;
}

function defaultStoreToggles() {
  return Object.fromEntries(STORE_KEYS.map((key) => [key, { enabled: true }]));
}

/**
 * The canonical settings shape and its current defaults. This is the single
 * source of truth the options page reads from and writes back to.
 */
export const DEFAULT_SETTINGS = Object.freeze({
  apiUrl: "http://127.0.0.1:8000",
  frontendUrls: Object.freeze([5173, 5174]),
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

  let frontendUrls = [...DEFAULT_SETTINGS.frontendUrls];
  if (src.frontendUrls !== undefined) {
    if (Array.isArray(src.frontendUrls)) {
      const seen = new Set();
      const ports = [];
      for (const entry of src.frontendUrls) {
        if (!isValidPort(entry)) continue;
        const port = toPort(entry);
        if (port === null || seen.has(port)) continue;
        seen.add(port);
        ports.push(port);
      }
      if (ports.length > 0) {
        frontendUrls = ports;
      } else {
        errors.push("frontendUrls invalide");
      }
    } else {
      errors.push("frontendUrls invalide");
    }
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
    settings: { apiUrl, frontendUrls, syncIntervalHours, cooldownMinutes, stores },
  };
}

/**
 * Derive the full list of frontend origins (127.0.0.1 + localhost) from a list
 * of ports. Used both to open the hub and to match open AdamHUB tabs.
 *
 * @param {number[]} ports
 * @returns {string[]}
 */
export function expandFrontendUrls(ports) {
  const urls = [];
  for (const port of ports) {
    urls.push(`http://127.0.0.1:${port}/`);
    urls.push(`http://localhost:${port}/`);
  }
  return urls;
}

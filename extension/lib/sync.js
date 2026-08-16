// Sync decision logic, import payload building and the per-store sync flow.
// Pure — chrome and fetch are injected by the caller (popup.js / background
// worker), never imported here, so both entry points share the same path.

import { getStore, STORE_KEYS } from "./stores.js";
import { TOKEN_STORAGE_KEY } from "./auth.js";

const MS_PER_MINUTE = 60 * 1000;
const IMPORT_PATH = "/api/v1/supermarket/connections/import";

const SAMESITE_MAP = {
  lax: "Lax",
  strict: "Strict",
  no_restriction: "None",
  none: "None",
};

/**
 * Convert a cooldown expressed in minutes to milliseconds.
 *
 * @param {number} cooldownMinutes
 * @returns {number}
 */
export function cooldownDurationMs(cooldownMinutes) {
  return cooldownMinutes * MS_PER_MINUTE;
}

/**
 * Decide whether a store should sync now, given its last sync timestamp and
 * the configured cooldown. A store that has never synced always qualifies;
 * a disabled store never does.
 *
 * @param {object} opts
 * @param {number|null|undefined} opts.lastSync
 * @param {number} opts.cooldownMinutes
 * @param {boolean} [opts.enabled=true]
 * @param {number} [opts.now=Date.now()]
 * @returns {boolean}
 */
export function shouldSync({ lastSync, cooldownMinutes, enabled = true, now = Date.now() }) {
  if (!enabled) return false;
  if (lastSync == null) return true;
  return now - lastSync >= cooldownDurationMs(cooldownMinutes);
}

/**
 * Map a raw `chrome.cookies` cookie to the shape the hub import endpoint
 * expects (sameSite re-capitalized, expirationDate rounded to `expires`).
 *
 * @param {object} cookie
 * @returns {object}
 */
export function normalizeCookie(cookie) {
  const out = {
    name: cookie.name,
    value: cookie.value,
    domain: cookie.domain,
    path: cookie.path,
    secure: !!cookie.secure,
    httpOnly: !!cookie.httpOnly,
  };
  if (cookie.sameSite) {
    out.sameSite = SAMESITE_MAP[cookie.sameSite] ?? cookie.sameSite;
  }
  if (cookie.expirationDate) {
    out.expires = Math.round(cookie.expirationDate);
  }
  return out;
}

/**
 * Build the body of `POST /api/v1/supermarket/connections/import`.
 *
 * @param {object} opts
 * @param {string} opts.storeKey
 * @param {object[]} opts.cookies  Already normalized cookies.
 * @param {boolean} [opts.activate=true]
 * @param {string} [opts.label=""]
 * @returns {object}
 */
export function buildPayload({ storeKey, cookies, activate = true, label = "" }) {
  return {
    store: storeKey,
    label,
    cookies,
    activate,
  };
}

/**
 * Build the sync surface on top of the injected chrome sub-APIs and fetch.
 * This is the single code path the popup's "Synchroniser maintenant" button
 * and the background worker both call: read cookies for a store, check its
 * session marker, POST the import payload and record `lastSync`.
 *
 * @param {object} deps
 * @param {chrome.storage.LocalStorageArea} deps.storage  chrome.storage.local
 * @param {chrome.cookies} deps.cookies  chrome.cookies
 * @param {Function} deps.fetchFn  fetch, injected so tests don't need the network
 * @param {string} deps.apiUrl  hub base URL (e.g. http://127.0.0.1:8000)
 * @param {Function} [deps.now=() => Date.now()]  clock, injectable for tests
 * @returns {{ readCookiesForStore, syncStore, syncAll }}
 */
export function createSync({ storage, cookies, fetchFn, apiUrl, now = () => Date.now() }) {
  /**
   * Read and normalize every cookie for a store's domains, deduped by
   * name|domain|path.
   *
   * @param {string} storeKey
   * @returns {Promise<object[]>} normalized cookies
   */
  async function readCookiesForStore(storeKey) {
    const def = getStore(storeKey);
    if (!def) return [];
    const list = [];
    const seen = new Set();
    for (const domain of def.cookieDomains) {
      const domainCookies = await cookies.getAll({ domain });
      for (const cookie of domainCookies) {
        const fp = `${cookie.name}|${cookie.domain}|${cookie.path}`;
        if (seen.has(fp)) continue;
        seen.add(fp);
        list.push(normalizeCookie(cookie));
      }
    }
    return list;
  }

  /**
   * POST the import payload for a store and translate the response into a
   * result. A 401 clears the cached token so the caller re-authenticates.
   *
   * @param {string} storeKey
   * @param {object[]} storeCookies
   * @param {string} token
   * @returns {Promise<object>}
   */
  async function postImport(storeKey, storeCookies, token) {
    const response = await fetchFn(`${apiUrl}${IMPORT_PATH}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(buildPayload({ storeKey, cookies: storeCookies })),
    });

    if (response.status === 401) {
      await storage.remove(TOKEN_STORAGE_KEY);
      return {
        ok: false,
        unauthorized: true,
        error: "Session expirée. Reconnecte-toi sur AdamHUB puis recommence.",
      };
    }
    if (!response.ok) {
      let detail = "";
      try {
        const data = await response.json();
        detail = data.detail ?? JSON.stringify(data);
      } catch {
        detail = await response.text();
      }
      return {
        ok: false,
        error: `HTTP ${response.status} — ${detail || "erreur inconnue"}`,
      };
    }
    return { ok: true, result: await response.json() };
  }

  async function recordLastSync(storeKey, timestamp) {
    const stored = await storage.get(["lastSync"]);
    const lastSync = { ...(stored.lastSync || {}), [storeKey]: timestamp };
    await storage.set({ lastSync });
  }

  /**
   * Run the full sync flow for a single store. Never throws — failures come
   * back as `{ ok: false, error }` so a caller can sync the remaining stores.
   *
   * @param {string} storeKey
   * @param {string} token
   * @returns {Promise<object>}
   */
  async function syncStore(storeKey, token) {
    const def = getStore(storeKey);
    if (!def) {
      return { storeKey, ok: false, error: `Enseigne inconnue : ${storeKey}` };
    }

    const storeCookies = await readCookiesForStore(storeKey);
    if (storeCookies.length === 0) {
      return {
        storeKey,
        ok: false,
        error: `Aucun cookie ${def.label} trouvé. Connecte-toi sur ${def.homepage} puis recommence.`,
      };
    }
    if (def.sessionMarker && !storeCookies.some((c) => c.name === def.sessionMarker)) {
      return {
        storeKey,
        ok: false,
        error: `Pas de session ${def.label} active (cookie ${def.sessionMarker} manquant). Connecte-toi puis recommence.`,
      };
    }

    const posted = await postImport(storeKey, storeCookies, token);
    if (!posted.ok) {
      return { storeKey, ...posted };
    }

    await recordLastSync(storeKey, now());
    return {
      storeKey,
      ok: true,
      cookiesCount: posted.result?.cookies_count ?? storeCookies.length,
      label: posted.result?.label ?? "",
    };
  }

  /**
   * Sync every store in order and return one result per store.
   *
   * @param {string} token
   * @returns {Promise<object[]>}
   */
  async function syncAll(token) {
    const results = [];
    for (const key of STORE_KEYS) {
      results.push(await syncStore(key, token));
    }
    return results;
  }

  return { readCookiesForStore, syncStore, syncAll };
}

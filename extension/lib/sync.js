// Sync decision logic and import payload building. Pure — chrome is injected
// by the caller (popup.js / background worker), never imported here.

const MS_PER_MINUTE = 60 * 1000;

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

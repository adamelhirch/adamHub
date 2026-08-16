// In-memory mocks for the chrome.* APIs used by lib/. Kept here so tests never
// touch the real browser: storage.local and scripting.executeScript are the only
// surfaces lib/ depends on today.

/**
 * Build an in-memory `chrome` mock.
 *
 * @param {object} [overrides]
 * @param {Function} [overrides.executeScript] Custom chrome.scripting.executeScript.
 * @param {object} [overrides.chrome] Extra chrome.* surfaces to attach.
 * @returns {{ chrome: object, storageLocal: object }}
 */
export function createMockChrome(overrides = {}) {
  const store = new Map();

  const storageLocal = {
    async get(keys) {
      if (keys == null) {
        return Object.fromEntries(store);
      }
      if (typeof keys === "string") {
        return store.has(keys) ? { [keys]: store.get(keys) } : {};
      }
      if (Array.isArray(keys)) {
        const out = {};
        for (const k of keys) {
          if (store.has(k)) out[k] = store.get(k);
        }
        return out;
      }
      if (typeof keys === "object") {
        const out = {};
        for (const [k, def] of Object.entries(keys)) {
          out[k] = store.has(k) ? store.get(k) : def;
        }
        return out;
      }
      return {};
    },
    async set(obj) {
      for (const [k, v] of Object.entries(obj)) store.set(k, v);
    },
    async remove(keys) {
      const list = Array.isArray(keys) ? keys : [keys];
      for (const k of list) store.delete(k);
    },
    _dump() {
      return Object.fromEntries(store);
    },
  };

  const scripting = {
    async executeScript(invocation) {
      if (overrides.executeScript) return overrides.executeScript(invocation);
      return [{ result: null }];
    },
  };

  const chrome = {
    storage: { local: storageLocal },
    scripting,
    ...(overrides.chrome ?? {}),
  };

  return { chrome, storageLocal, scripting };
}

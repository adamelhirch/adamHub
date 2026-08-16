// In-memory mocks for the chrome.* surfaces the background worker depends on
// (storage.local, storage.sync, cookies, alarms, tabs, notifications, runtime,
// scripting). Kept here so worker.test.js never touches a real browser and can
// assert on the exact calls the worker made.

function makeArea(map) {
  return {
    async get(keys) {
      if (keys == null) return Object.fromEntries(map);
      if (typeof keys === "string") {
        return map.has(keys) ? { [keys]: map.get(keys) } : {};
      }
      if (Array.isArray(keys)) {
        const out = {};
        for (const k of keys) if (map.has(k)) out[k] = map.get(k);
        return out;
      }
      if (typeof keys === "object") {
        const out = {};
        for (const [k, def] of Object.entries(keys)) out[k] = map.has(k) ? map.get(k) : def;
        return out;
      }
      return {};
    },
    async set(obj) {
      for (const [k, v] of Object.entries(obj)) map.set(k, v);
    },
    async remove(keys) {
      const list = Array.isArray(keys) ? keys : [keys];
      for (const k of list) map.delete(k);
    },
    _dump() {
      return Object.fromEntries(map);
    },
  };
}

/**
 * Build an in-memory `chrome` mock for the background worker.
 *
 * @param {object} [overrides]
 * @param {object} [overrides.chrome] Extra chrome.* surfaces to attach/override.
 * @returns {{ chrome, storageLocal, storageSync, scripting, cookies, alarms, tabs, notifications, runtime }}
 */
export function createWorkerChrome(overrides = {}) {
  const storageLocal = makeArea(new Map());
  const storageSync = makeArea(new Map());

  const scripting = {
    async executeScript() {
      return [{ result: null }];
    },
  };

  const cookies = {
    // domain -> array of raw cookies
    list: {},
    async getAll(query) {
      return cookies.list[query.domain] ?? [];
    },
  };

  const alarms = {
    created: [],
    cleared: [],
    async create(name, info) {
      alarms.created.push({ name, info });
    },
    async clear(name) {
      alarms.cleared.push(name);
    },
  };

  const notifications = {
    created: [],
    async create(id, options) {
      notifications.created.push({ id, options });
      return id;
    },
  };

  const tabs = {
    created: [],
    async create(opts) {
      tabs.created.push(opts);
      return { id: 1, ...opts };
    },
    async query() {
      return [];
    },
  };

  const runtime = {
    getURL(path) {
      return `chrome-extension://test/${path}`;
    },
  };

  const chrome = {
    storage: { local: storageLocal, sync: storageSync },
    scripting,
    cookies,
    alarms,
    notifications,
    tabs,
    runtime,
    ...(overrides.chrome ?? {}),
  };

  return { chrome, storageLocal, storageSync, scripting, cookies, alarms, notifications, tabs, runtime };
}

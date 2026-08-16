// Auth helpers: a cached-token store backed by chrome.storage.local, plus the
// reader that pulls the JWT out of an open AdamHUB tab's localStorage. chrome
// is injected at construction time so this stays testable without a browser.

export const TOKEN_LOCALSTORAGE_KEY = "adamhub_token";
export const TOKEN_STORAGE_KEY = "token";

/**
 * Build the auth surface on top of the injected chrome sub-APIs.
 *
 * @param {object} deps
 * @param {chrome.storage.LocalStorageArea} deps.storage  chrome.storage.local
 * @param {chrome.scripting} deps.scripting  chrome.scripting
 * @returns {{ getToken, setToken, clearToken, readTokenFromTab }}
 */
export function createAuth({ storage, scripting }) {
  async function getToken() {
    const data = await storage.get([TOKEN_STORAGE_KEY]);
    return data[TOKEN_STORAGE_KEY] ?? null;
  }

  async function setToken(token) {
    await storage.set({ [TOKEN_STORAGE_KEY]: token });
  }

  async function clearToken() {
    await storage.remove(TOKEN_STORAGE_KEY);
  }

  async function readTokenFromTab(tabId) {
    try {
      const results = await scripting.executeScript({
        target: { tabId },
        func: (key) => {
          try {
            return window.localStorage.getItem(key);
          } catch {
            return null;
          }
        },
        args: [TOKEN_LOCALSTORAGE_KEY],
      });
      if (!results || results.length === 0) return null;
      return results[0]?.result ?? null;
    } catch (err) {
      console.warn("[AdamHUB] readTokenFromTab failed:", err);
      return null;
    }
  }

  return { getToken, setToken, clearToken, readTokenFromTab };
}

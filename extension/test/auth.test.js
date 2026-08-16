import { describe, it, expect, vi } from "vitest";
import { createMockChrome } from "./helpers/chrome.js";
import {
  createAuth,
  TOKEN_LOCALSTORAGE_KEY,
  TOKEN_STORAGE_KEY,
} from "../lib/auth.js";

describe("auth token cache", () => {
  it("returns null when no token is cached", async () => {
    const { chrome } = createMockChrome();
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });
    expect(await auth.getToken()).toBeNull();
  });

  it("sets and reads the token back", async () => {
    const { chrome, storageLocal } = createMockChrome();
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });

    await auth.setToken("jwt-abc");

    expect(storageLocal._dump()).toEqual({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    expect(await auth.getToken()).toBe("jwt-abc");
  });

  it("clears the cached token", async () => {
    const { chrome, storageLocal } = createMockChrome();
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });

    await auth.setToken("jwt-abc");
    await auth.clearToken();

    expect(await auth.getToken()).toBeNull();
    expect(storageLocal._dump()).toEqual({});
  });

  it("treats a null cached value as absent", async () => {
    const { chrome, storageLocal } = createMockChrome();
    await storageLocal.set({ [TOKEN_STORAGE_KEY]: null });
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });

    expect(await auth.getToken()).toBeNull();
  });
});

describe("auth readTokenFromTab", () => {
  it("reads the token from an injected tab script", async () => {
    let captured = null;
    const { chrome } = createMockChrome({
      executeScript: async (invocation) => {
        captured = invocation;
        return [{ result: "jwt-from-tab" }];
      },
    });
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });

    expect(await auth.readTokenFromTab(42)).toBe("jwt-from-tab");
    expect(captured.target.tabId).toBe(42);
    expect(captured.args).toEqual([TOKEN_LOCALSTORAGE_KEY]);
  });

  it("returns null when the tab has no token", async () => {
    const { chrome } = createMockChrome({
      executeScript: async () => [{ result: null }],
    });
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });

    expect(await auth.readTokenFromTab(1)).toBeNull();
  });

  it("returns null when executeScript returns an empty result set", async () => {
    const { chrome } = createMockChrome({ executeScript: async () => [] });
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });

    expect(await auth.readTokenFromTab(1)).toBeNull();
  });

  it("returns null instead of throwing when executeScript fails", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { chrome } = createMockChrome({
      executeScript: async () => {
        throw new Error("no tab");
      },
    });
    const auth = createAuth({ storage: chrome.storage.local, scripting: chrome.scripting });

    await expect(auth.readTokenFromTab(999)).resolves.toBeNull();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe("auth constants", () => {
  it("keeps the hub-localStorage and storage keys stable", () => {
    expect(TOKEN_LOCALSTORAGE_KEY).toBe("adamhub_token");
    expect(TOKEN_STORAGE_KEY).toBe("token");
  });
});

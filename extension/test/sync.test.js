import { describe, it, expect } from "vitest";
import { createMockChrome } from "./helpers/chrome.js";
import { STORE_KEYS } from "../lib/stores.js";
import {
  cooldownDurationMs,
  shouldSync,
  normalizeCookie,
  buildPayload,
  createSync,
} from "../lib/sync.js";

const HUB_URL = "http://127.0.0.1:8000";
const IMPORT_URL = `${HUB_URL}/api/v1/supermarket/connections/import`;

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return body;
    },
    async text() {
      return JSON.stringify(body);
    },
  };
}

function makeSync({ cookies = [], fetchImpl } = {}) {
  const { chrome, storageLocal } = createMockChrome({
    getAllCookies: async () => cookies,
  });
  const fetchFn = fetchImpl ?? (async () => jsonResponse(200, { cookies_count: cookies.length, label: "Moi" }));
  const sync = createSync({
    storage: chrome.storage.local,
    cookies: chrome.cookies,
    fetchFn,
    apiUrl: HUB_URL,
    now: () => NOW,
  });
  return { sync, storageLocal };
}

const NOW = 1_700_000_000_000;

describe("cooldownDurationMs", () => {
  it("converts minutes to milliseconds", () => {
    expect(cooldownDurationMs(30)).toBe(30 * 60 * 1000);
    expect(cooldownDurationMs(0)).toBe(0);
    expect(cooldownDurationMs(1)).toBe(60_000);
  });
});

describe("shouldSync", () => {
  const now = 1_000_000;

  it("syncs a store that has never been synced", () => {
    expect(shouldSync({ lastSync: null, cooldownMinutes: 30, now })).toBe(true);
    expect(shouldSync({ lastSync: undefined, cooldownMinutes: 30, now })).toBe(true);
  });

  it("never syncs a disabled store", () => {
    expect(
      shouldSync({ lastSync: null, cooldownMinutes: 30, enabled: false, now }),
    ).toBe(false);
  });

  it("blocks a sync inside the cooldown window", () => {
    const lastSync = now - 30 * 60 * 1000 + 1;
    expect(shouldSync({ lastSync, cooldownMinutes: 30, now })).toBe(false);
  });

  it("allows a sync once the cooldown has fully elapsed", () => {
    const lastSync = now - 30 * 60 * 1000;
    expect(shouldSync({ lastSync, cooldownMinutes: 30, now })).toBe(true);
    expect(shouldSync({ lastSync: now - 31 * 60 * 1000, cooldownMinutes: 30, now })).toBe(true);
  });
});

describe("normalizeCookie", () => {
  it("maps a chrome cookie to the import shape", () => {
    const cookie = {
      name: "FRO_CONNECTED",
      value: "abc",
      domain: ".carrefour.fr",
      path: "/",
      secure: true,
      httpOnly: true,
      sameSite: "no_restriction",
      expirationDate: 1_720_000_000.9,
    };
    expect(normalizeCookie(cookie)).toEqual({
      name: "FRO_CONNECTED",
      value: "abc",
      domain: ".carrefour.fr",
      path: "/",
      secure: true,
      httpOnly: true,
      sameSite: "None",
      expires: 1_720_000_001,
    });
  });

  it("normalizes every known sameSite value and passes unknowns through", () => {
    expect(normalizeCookie({ sameSite: "lax" }).sameSite).toBe("Lax");
    expect(normalizeCookie({ sameSite: "strict" }).sameSite).toBe("Strict");
    expect(normalizeCookie({ sameSite: "none" }).sameSite).toBe("None");
    expect(normalizeCookie({ sameSite: "weird" }).sameSite).toBe("weird");
  });

  it("omits sameSite and expires when they are absent", () => {
    const out = normalizeCookie({ name: "a", value: "b", domain: "d", path: "/" });
    expect(out).not.toHaveProperty("sameSite");
    expect(out).not.toHaveProperty("expires");
  });

  it("coerces secure and httpOnly to booleans", () => {
    const out = normalizeCookie({ name: "a", value: "b", domain: "d", path: "/" });
    expect(out.secure).toBe(false);
    expect(out.httpOnly).toBe(false);
  });
});

describe("buildPayload", () => {
  const cookies = [{ name: "a", value: "1" }, { name: "b", value: "2" }];

  it("builds an import payload with store, empty label and activate by default", () => {
    expect(buildPayload({ storeKey: "carrefour", cookies })).toEqual({
      store: "carrefour",
      label: "",
      cookies,
      activate: true,
    });
  });

  it("honours explicit activate and label overrides", () => {
    expect(
      buildPayload({ storeKey: "auchan", cookies, activate: false, label: "Moi" }),
    ).toEqual({
      store: "auchan",
      label: "Moi",
      cookies,
      activate: false,
    });
  });
});

describe("createSync.readCookiesForStore", () => {
  it("normalizes and dedupes cookies across the store's domains", async () => {
    // The mock returns the same list for every domain query, so a cookie
    // matching both ".carrefour.fr" and "www.carrefour.fr" comes back twice
    // and must be collapsed by name|domain|path.
    const cookies = [
      {
        name: "FRO_CONNECTED",
        value: "abc",
        domain: ".carrefour.fr",
        path: "/",
        secure: true,
        httpOnly: true,
        sameSite: "no_restriction",
        expirationDate: 1_720_000_000.9,
      },
    ];
    const { sync } = makeSync({ cookies });

    const out = await sync.readCookiesForStore("carrefour");

    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({
      name: "FRO_CONNECTED",
      value: "abc",
      domain: ".carrefour.fr",
      path: "/",
      secure: true,
      httpOnly: true,
      sameSite: "None",
      expires: 1_720_000_001,
    });
  });
});

describe("createSync.syncStore", () => {
  it("reads cookies, checks the session marker, POSTs the payload and records lastSync", async () => {
    const cookies = [
      { name: "FRO_CONNECTED", value: "abc", domain: ".carrefour.fr", path: "/", secure: true, httpOnly: true },
      { name: "ot", value: "x", domain: "www.carrefour.fr", path: "/" },
    ];
    let captured = null;
    const fetchImpl = async (url, init) => {
      captured = { url, init };
      return jsonResponse(200, { cookies_count: 2, label: "Moi" });
    };
    const { sync, storageLocal } = makeSync({ cookies, fetchImpl });

    const result = await sync.syncStore("carrefour", "jwt-1");

    expect(result).toEqual({
      storeKey: "carrefour",
      ok: true,
      cookiesCount: 2,
      label: "Moi",
    });

    expect(captured.url).toBe(IMPORT_URL);
    expect(captured.init.method).toBe("POST");
    expect(captured.init.headers.Authorization).toBe("Bearer jwt-1");
    const body = JSON.parse(captured.init.body);
    expect(body.store).toBe("carrefour");
    expect(body.activate).toBe(true);
    expect(body.label).toBe("");
    expect(body.cookies).toHaveLength(2);

    expect(storageLocal._dump().lastSync).toEqual({ carrefour: NOW });
  });

  it("fails on an unknown store without touching cookies or storage", async () => {
    const { sync, storageLocal } = makeSync({ cookies: [] });

    const result = await sync.syncStore("toto", "jwt-1");

    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/Enseigne inconnue/);
    expect(storageLocal._dump()).toEqual({});
  });

  it("fails without POSTing when no cookies are found", async () => {
    let posted = false;
    const fetchImpl = async () => {
      posted = true;
      return jsonResponse(200, {});
    };
    const { sync, storageLocal } = makeSync({ cookies: [], fetchImpl });

    const result = await sync.syncStore("carrefour", "jwt-1");

    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/Aucun cookie Carrefour/);
    expect(posted).toBe(false);
    expect(storageLocal._dump()).toEqual({});
  });

  it("fails without POSTing when the session marker cookie is missing", async () => {
    let posted = false;
    const fetchImpl = async () => {
      posted = true;
      return jsonResponse(200, {});
    };
    const cookies = [{ name: "other", value: "x", domain: ".carrefour.fr", path: "/" }];
    const { sync, storageLocal } = makeSync({ cookies, fetchImpl });

    const result = await sync.syncStore("carrefour", "jwt-1");

    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/FRO_CONNECTED/);
    expect(posted).toBe(false);
    expect(storageLocal._dump()).toEqual({});
  });

  it("clears the cached token on a 401 and reports unauthorized without recording lastSync", async () => {
    const { chrome, storageLocal } = createMockChrome({
      getAllCookies: async () => [
        { name: "FRO_CONNECTED", value: "a", domain: ".carrefour.fr", path: "/" },
      ],
    });
    await storageLocal.set({ token: "jwt-stale" });
    const sync = createSync({
      storage: chrome.storage.local,
      cookies: chrome.cookies,
      fetchFn: async () => jsonResponse(401, { detail: "unauthorized" }),
      apiUrl: HUB_URL,
      now: () => NOW,
    });

    const result = await sync.syncStore("carrefour", "jwt-stale");

    expect(result.ok).toBe(false);
    expect(result.unauthorized).toBe(true);
    expect(result.error).toMatch(/Session expirée/);
    expect(storageLocal._dump()).toEqual({});
  });

  it("surfaces the hub error detail on a non-2xx response", async () => {
    const cookies = [{ name: "FRO_CONNECTED", value: "a", domain: ".carrefour.fr", path: "/" }];
    const { sync, storageLocal } = makeSync({
      cookies,
      fetchImpl: async () => jsonResponse(422, { detail: "bad payload" }),
    });

    const result = await sync.syncStore("carrefour", "jwt-1");

    expect(result.ok).toBe(false);
    expect(result.unauthorized).toBeUndefined();
    expect(result.error).toContain("422");
    expect(result.error).toContain("bad payload");
    expect(storageLocal._dump()).toEqual({});
  });
});

describe("createSync.syncAll", () => {
  it("runs every store and returns one result per store", async () => {
    const { sync } = makeSync({ cookies: [] });

    const results = await sync.syncAll("jwt-1");

    expect(results.map((r) => r.storeKey).sort()).toEqual([...STORE_KEYS].sort());
    expect(results.every((r) => r.ok === false)).toBe(true);
  });
});

import { describe, it, expect, vi } from "vitest";
import {
  createWorker,
  matchStoreByUrl,
  ALARM_NAME,
  LAST_SYNC_KEY,
  IMPORT_PATH,
} from "../lib/worker.js";
import { SETTINGS_STORAGE_KEY } from "../lib/settings.js";
import { TOKEN_STORAGE_KEY } from "../lib/auth.js";
import { createWorkerChrome } from "./helpers/worker-chrome.js";

const DEFAULT_SETTINGS = {
  apiUrl: "http://127.0.0.1:8000",
  frontendUrls: [5173, 5174],
  syncIntervalHours: 6,
  cooldownMinutes: 30,
  stores: {
    carrefour: { enabled: true },
    intermarche: { enabled: true },
    leclerc: { enabled: true },
    auchan: { enabled: true },
  },
};

function carrefourSessionCookie(extra = {}) {
  return { name: "FRO_CONNECTED", value: "1", domain: ".carrefour.fr", path: "/", ...extra };
}

describe("matchStoreByUrl", () => {
  it("maps a tab URL to its store", () => {
    expect(matchStoreByUrl("https://www.carrefour.fr/panier")).toBe("carrefour");
    expect(matchStoreByUrl("https://www.intermarche.com/")).toBe("intermarche");
    expect(matchStoreByUrl("https://www.leclercdrive.fr/")).toBe("leclerc");
    expect(matchStoreByUrl("https://www.auchan.fr/rayons")).toBe("auchan");
  });

  it("matches subdomains through the dotted cookie domain", () => {
    expect(matchStoreByUrl("https://courses.intermarche.com/")).toBe("intermarche");
    expect(matchStoreByUrl("https://foo.carrefour.fr/")).toBe("carrefour");
  });

  it("rejects unrelated and malformed URLs", () => {
    expect(matchStoreByUrl("https://example.com/")).toBeNull();
    expect(matchStoreByUrl("https://carrefour.fr.evil.com/")).toBeNull();
    expect(matchStoreByUrl("not a url")).toBeNull();
    expect(matchStoreByUrl(null)).toBeNull();
  });
});

describe("scheduleAlarm", () => {
  it("schedules a periodic alarm at the configured frequency", async () => {
    const m = createWorkerChrome();
    await m.storageSync.set({ [SETTINGS_STORAGE_KEY]: { syncIntervalHours: 2 } });
    const worker = createWorker({ chrome: m.chrome });

    await worker.scheduleAlarm();

    expect(m.alarms.created).toEqual([
      { name: ALARM_NAME, info: { periodInMinutes: 120 } },
    ]);
  });

  it("falls back to the default frequency when no settings are stored", async () => {
    const m = createWorkerChrome();
    const worker = createWorker({ chrome: m.chrome });

    await worker.scheduleAlarm();

    expect(m.alarms.created).toEqual([
      { name: ALARM_NAME, info: { periodInMinutes: 6 * 60 } },
    ]);
  });
});

describe("handleInstalled", () => {
  it("schedules the alarm, then notifies a reconnect when no token is cached", async () => {
    const m = createWorkerChrome();
    const worker = createWorker({ chrome: m.chrome });

    await worker.handleInstalled({ reason: "install" });

    expect(m.alarms.created).toHaveLength(1);
    expect(m.notifications.created).toHaveLength(1);
    expect(m.notifications.created[0].options.message).toMatch(/reconnecte/i);
  });

  it("opens the hub when the reconnect notification is clicked", async () => {
    const m = createWorkerChrome();
    const worker = createWorker({ chrome: m.chrome });

    await worker.handleInstalled({ reason: "install" });
    const { id } = m.notifications.created[0];
    await worker.handleNotificationClicked(id);

    expect(m.tabs.created).toEqual([{ url: "http://127.0.0.1:5173/" }]);
  });

  it("syncs immediately when a token is already cached", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    m.cookies.list[".carrefour.fr"] = [carrefourSessionCookie()];
    const fetchFn = vi.fn(async () => ({ ok: true, status: 200 }));
    const worker = createWorker({ chrome: m.chrome, fetchFn, now: () => 1_000 });

    await worker.handleInstalled({ reason: "install" });

    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(m.notifications.created).toHaveLength(0);
    expect((await m.storageLocal.get(LAST_SYNC_KEY))[LAST_SYNC_KEY]).toEqual({
      carrefour: 1_000,
    });
  });

  it("only reschedules on update without a reconnect notification", async () => {
    const m = createWorkerChrome();
    const worker = createWorker({ chrome: m.chrome });

    await worker.handleInstalled({ reason: "update" });

    expect(m.alarms.created).toHaveLength(1);
    expect(m.notifications.created).toHaveLength(0);
  });
});

describe("handleAlarm", () => {
  it("syncs every store when the sync alarm fires", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    m.cookies.list[".carrefour.fr"] = [carrefourSessionCookie()];
    const fetchFn = vi.fn(async () => ({ ok: true, status: 200 }));
    const worker = createWorker({ chrome: m.chrome, fetchFn, now: () => 5_000 });

    await worker.handleAlarm({ name: ALARM_NAME });

    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("ignores unrelated alarms", async () => {
    const m = createWorkerChrome();
    const fetchFn = vi.fn();
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    await worker.handleAlarm({ name: "other-alarm" });

    expect(fetchFn).not.toHaveBeenCalled();
  });
});

describe("handleTabUpdated", () => {
  it("syncs the matching store when a store tab finishes loading", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    m.cookies.list[".carrefour.fr"] = [carrefourSessionCookie()];
    const fetchFn = vi.fn(async () => ({ ok: true, status: 200 }));
    const worker = createWorker({ chrome: m.chrome, fetchFn, now: () => 10_000 });

    await worker.handleTabUpdated(
      42,
      { status: "complete" },
      { url: "https://www.carrefour.fr/" },
    );

    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn.mock.calls[0][0]).toBe(
      `http://127.0.0.1:8000${IMPORT_PATH}`,
    );
  });

  it("ignores tabs that are not done loading", async () => {
    const m = createWorkerChrome();
    const fetchFn = vi.fn();
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    await worker.handleTabUpdated(1, { status: "loading" }, { url: "https://www.carrefour.fr/" });

    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("ignores tabs on unrelated domains", async () => {
    const m = createWorkerChrome();
    const fetchFn = vi.fn();
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    await worker.handleTabUpdated(1, { status: "complete" }, { url: "https://example.com/" });

    expect(fetchFn).not.toHaveBeenCalled();
  });
});

describe("syncStore", () => {
  it("skips a disabled store without any network call", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    const fetchFn = vi.fn();
    const worker = createWorker({ chrome: m.chrome, fetchFn });
    const settings = {
      ...DEFAULT_SETTINGS,
      stores: { ...DEFAULT_SETTINGS.stores, carrefour: { enabled: false } },
    };

    const result = await worker.syncStore("carrefour", settings);

    expect(result).toBe("disabled");
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("skips a store inside the cooldown window", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    await m.storageLocal.set({ [LAST_SYNC_KEY]: { carrefour: 60_000 } });
    const fetchFn = vi.fn();
    const worker = createWorker({ chrome: m.chrome, fetchFn, now: () => 60_000 + 5 * 60_000 });

    const result = await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(result).toBe("cooldown");
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("syncs a store once the cooldown has elapsed", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    await m.storageLocal.set({ [LAST_SYNC_KEY]: { carrefour: 0 } });
    m.cookies.list[".carrefour.fr"] = [carrefourSessionCookie()];
    const fetchFn = vi.fn(async () => ({ ok: true, status: 200 }));
    const worker = createWorker({ chrome: m.chrome, fetchFn, now: () => 31 * 60_000 });

    const result = await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(result).toBe("synced");
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect((await m.storageLocal.get(LAST_SYNC_KEY))[LAST_SYNC_KEY]).toEqual({
      carrefour: 31 * 60_000,
    });
  });

  it("skips silently when the store has no cookies", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    const fetchFn = vi.fn();
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    const result = await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(result).toBe("no-cookies");
    expect(fetchFn).not.toHaveBeenCalled();
    expect(m.notifications.created).toHaveLength(0);
  });

  it("skips silently when the session marker cookie is missing", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-abc" });
    m.cookies.list[".carrefour.fr"] = [{ name: "other", value: "1", domain: ".carrefour.fr", path: "/" }];
    const fetchFn = vi.fn();
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    const result = await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(result).toBe("no-session");
    expect(fetchFn).not.toHaveBeenCalled();
    expect(m.notifications.created).toHaveLength(0);
  });

  it("clears the cached token and notifies a reconnect on 401", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-expired" });
    m.cookies.list[".carrefour.fr"] = [carrefourSessionCookie()];
    const fetchFn = vi.fn(async () => ({ ok: false, status: 401 }));
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    const result = await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(result).toBe("unauthorized");
    expect((await m.storageLocal.get(TOKEN_STORAGE_KEY))[TOKEN_STORAGE_KEY]).toBeUndefined();
    expect(m.notifications.created).toHaveLength(1);
    expect(m.notifications.created[0].options.message).toMatch(/reconnecte/i);
    // clicking that notification reopens the hub
    await worker.handleNotificationClicked(m.notifications.created[0].id);
    expect(m.tabs.created).toEqual([{ url: "http://127.0.0.1:5173/" }]);
  });

  it("notifies on a non-401 HTTP error without clearing the token", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-ok" });
    m.cookies.list[".carrefour.fr"] = [carrefourSessionCookie()];
    const fetchFn = vi.fn(async () => ({ ok: false, status: 500, json: async () => ({ detail: "boom" }) }));
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    const result = await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(result).toBe("http-error");
    expect((await m.storageLocal.get(TOKEN_STORAGE_KEY))[TOKEN_STORAGE_KEY]).toBe("jwt-ok");
    expect(m.notifications.created).toHaveLength(1);
    expect(m.notifications.created[0].options.message).toMatch(/500/);
  });

  it("notifies when the fetch itself fails", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-ok" });
    m.cookies.list[".carrefour.fr"] = [carrefourSessionCookie()];
    const fetchFn = vi.fn(async () => {
      throw new Error("network down");
    });
    const worker = createWorker({ chrome: m.chrome, fetchFn });

    const result = await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(result).toBe("network-error");
    expect(m.notifications.created).toHaveLength(1);
    expect(m.notifications.created[0].options.message).toMatch(/network down/);
  });

  it("POSTs the import payload with the cached bearer token on success", async () => {
    const m = createWorkerChrome();
    await m.storageLocal.set({ [TOKEN_STORAGE_KEY]: "jwt-ok" });
    m.cookies.list[".carrefour.fr"] = [
      carrefourSessionCookie(),
      { name: "other", value: "x", domain: ".carrefour.fr", path: "/" },
    ];
    const fetchFn = vi.fn(async () => ({ ok: true, status: 200 }));
    const worker = createWorker({ chrome: m.chrome, fetchFn, now: () => 42 });

    await worker.syncStore("carrefour", DEFAULT_SETTINGS);

    expect(fetchFn).toHaveBeenCalledTimes(1);
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe(`http://127.0.0.1:8000${IMPORT_PATH}`);
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer jwt-ok");
    const body = JSON.parse(init.body);
    expect(body.store).toBe("carrefour");
    expect(body.activate).toBe(true);
    expect(body.cookies.map((c) => c.name).sort()).toEqual(["FRO_CONNECTED", "other"]);
  });
});

describe("handleNotificationClicked", () => {
  it("ignores notifications that are not reconnect prompts", async () => {
    const m = createWorkerChrome();
    const worker = createWorker({ chrome: m.chrome });

    await worker.handleNotificationClicked("unknown-id");

    expect(m.tabs.created).toHaveLength(0);
  });
});

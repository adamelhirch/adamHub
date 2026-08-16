import { describe, it, expect } from "vitest";
import {
  DEFAULT_SETTINGS,
  SETTINGS_STORAGE_KEY,
  validateSettings,
  frontendOrigins,
  matchesFrontend,
} from "../lib/settings.js";

describe("DEFAULT_SETTINGS", () => {
  it("matches the current hard-coded extension values", () => {
    expect(DEFAULT_SETTINGS.apiUrl).toBe("http://127.0.0.1:8000");
    expect(DEFAULT_SETTINGS.frontendUrl).toBe("http://localhost:5173");
    expect(DEFAULT_SETTINGS.syncIntervalHours).toBe(6);
    expect(DEFAULT_SETTINGS.cooldownMinutes).toBe(30);
  });

  it("enables every store by default", () => {
    expect(DEFAULT_SETTINGS.stores).toEqual({
      carrefour: { enabled: true },
      intermarche: { enabled: true },
      leclerc: { enabled: true },
      auchan: { enabled: true },
    });
  });
});

describe("validateSettings", () => {
  it("returns clean defaults for empty input", () => {
    const r = validateSettings(undefined);
    expect(r.valid).toBe(true);
    expect(r.errors).toEqual([]);
    expect(r.settings).toEqual(DEFAULT_SETTINGS);
  });

  it("keeps valid overrides and fills in the rest", () => {
    const r = validateSettings({
      apiUrl: "http://hub.example.com:9000",
      frontendUrl: "http://localhost:5174",
      syncIntervalHours: 12,
      cooldownMinutes: 15,
      stores: { carrefour: { enabled: false } },
    });
    expect(r.valid).toBe(true);
    expect(r.errors).toEqual([]);
    expect(r.settings.apiUrl).toBe("http://hub.example.com:9000");
    expect(r.settings.frontendUrl).toBe("http://localhost:5174");
    expect(r.settings.syncIntervalHours).toBe(12);
    expect(r.settings.cooldownMinutes).toBe(15);
    expect(r.settings.stores.carrefour.enabled).toBe(false);
    expect(r.settings.stores.intermarche.enabled).toBe(true);
  });

  it("rejects an invalid apiUrl and falls back to the default", () => {
    const r = validateSettings({ apiUrl: "pas-une-url" });
    expect(r.valid).toBe(false);
    expect(r.errors).toContain("apiUrl invalide");
    expect(r.settings.apiUrl).toBe(DEFAULT_SETTINGS.apiUrl);
  });

  it("accepts http and https frontend URLs", () => {
    expect(validateSettings({ frontendUrl: "http://localhost:5173" }).valid).toBe(true);
    expect(
      validateSettings({ frontendUrl: "https://app.adamhub.example/" }).settings.frontendUrl,
    ).toBe("https://app.adamhub.example/");
  });

  it("rejects a malformed or non-http(s) frontend URL and falls back to the default", () => {
    for (const bad of ["ftp://localhost:5173", "localhost:5173", "pas-une-url", "http://", ""]) {
      const r = validateSettings({ frontendUrl: bad });
      expect(r.valid, `frontendUrl "${bad}"`).toBe(false);
      expect(r.errors).toContain("frontendUrl invalide");
      expect(r.settings.frontendUrl).toBe(DEFAULT_SETTINGS.frontendUrl);
    }
  });

  it("falls back when frontendUrl is not a string", () => {
    for (const bad of [5173, null, ["http://localhost:5173"]]) {
      const r = validateSettings({ frontendUrl: bad });
      expect(r.valid).toBe(false);
      expect(r.settings.frontendUrl).toBe(DEFAULT_SETTINGS.frontendUrl);
    }
  });

  it("rejects non-positive sync intervals and negative cooldowns", () => {
    const r = validateSettings({ syncIntervalHours: 0, cooldownMinutes: -5 });
    expect(r.valid).toBe(false);
    expect(r.errors).toContain("syncIntervalHours invalide");
    expect(r.errors).toContain("cooldownMinutes invalide");
    expect(r.settings.syncIntervalHours).toBe(DEFAULT_SETTINGS.syncIntervalHours);
    expect(r.settings.cooldownMinutes).toBe(DEFAULT_SETTINGS.cooldownMinutes);
  });

  it("drops unknown store toggles and defaults the rest to enabled", () => {
    const r = validateSettings({ stores: { carrefour: { enabled: false }, unknown: { enabled: false } } });
    expect(r.settings.stores).toEqual({
      carrefour: { enabled: false },
      intermarche: { enabled: true },
      leclerc: { enabled: true },
      auchan: { enabled: true },
    });
  });

  it("returns fresh objects rather than shared references", () => {
    const r = validateSettings(undefined);
    expect(r.settings).not.toBe(DEFAULT_SETTINGS);
    expect(r.settings.stores).not.toBe(DEFAULT_SETTINGS.stores);
  });
});

describe("frontendOrigins", () => {
  it("expands localhost to its loopback alias and vice-versa", () => {
    expect(frontendOrigins("http://localhost:5173")).toEqual([
      "http://localhost:5173",
      "http://127.0.0.1:5173",
    ]);
    expect(frontendOrigins("http://127.0.0.1:5173")).toEqual([
      "http://127.0.0.1:5173",
      "http://localhost:5173",
    ]);
  });

  it("keeps a single origin for non-loopback hosts", () => {
    expect(frontendOrigins("https://app.adamhub.example")).toEqual([
      "https://app.adamhub.example",
    ]);
  });

  it("normalizes a trailing slash and default port", () => {
    expect(frontendOrigins("http://localhost:5173/")).toEqual([
      "http://localhost:5173",
      "http://127.0.0.1:5173",
    ]);
  });

  it("returns an empty list for a malformed URL", () => {
    expect(frontendOrigins("pas-une-url")).toEqual([]);
    expect(frontendOrigins("")).toEqual([]);
  });
});

describe("matchesFrontend", () => {
  it("matches the configured origin exactly and with a path", () => {
    expect(matchesFrontend("http://localhost:5173", "http://localhost:5173")).toBe(true);
    expect(matchesFrontend("http://localhost:5173/", "http://localhost:5173")).toBe(true);
    expect(matchesFrontend("http://localhost:5173/foo/bar", "http://localhost:5173")).toBe(true);
  });

  it("matches the loopback alias host", () => {
    expect(matchesFrontend("http://127.0.0.1:5173/", "http://localhost:5173")).toBe(true);
    expect(matchesFrontend("http://localhost:5174", "http://127.0.0.1:5174")).toBe(true);
  });

  it("does not match a different port, scheme or host", () => {
    expect(matchesFrontend("http://localhost:5174", "http://localhost:5173")).toBe(false);
    expect(matchesFrontend("https://localhost:5173", "http://localhost:5173")).toBe(false);
    expect(matchesFrontend("http://example.com:5173", "http://localhost:5173")).toBe(false);
  });

  it("ignores non-http and malformed tab URLs", () => {
    expect(matchesFrontend("chrome://extensions", "http://localhost:5173")).toBe(false);
    expect(matchesFrontend("", "http://localhost:5173")).toBe(false);
    expect(matchesFrontend(null, "http://localhost:5173")).toBe(false);
  });
});

describe("SETTINGS_STORAGE_KEY", () => {
  it("stores settings under a stable chrome.storage.sync key", () => {
    expect(SETTINGS_STORAGE_KEY).toBe("settings");
  });
});

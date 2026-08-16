import { describe, it, expect } from "vitest";
import {
  DEFAULT_SETTINGS,
  validateSettings,
  expandFrontendUrls,
} from "../lib/settings.js";

describe("DEFAULT_SETTINGS", () => {
  it("matches the current hard-coded extension values", () => {
    expect(DEFAULT_SETTINGS.apiUrl).toBe("http://127.0.0.1:8000");
    expect(DEFAULT_SETTINGS.frontendUrls).toEqual([5173, 5174]);
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
      frontendUrls: [5173, 5175],
      syncIntervalHours: 12,
      cooldownMinutes: 15,
      stores: { carrefour: { enabled: false } },
    });
    expect(r.valid).toBe(true);
    expect(r.errors).toEqual([]);
    expect(r.settings.apiUrl).toBe("http://hub.example.com:9000");
    expect(r.settings.frontendUrls).toEqual([5173, 5175]);
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

  it("filters non-port entries and dedupes the frontendUrls list", () => {
    const r = validateSettings({ frontendUrls: [5173, 5173, 70000, "abc", 5174] });
    expect(r.valid).toBe(true);
    expect(r.settings.frontendUrls).toEqual([5173, 5174]);
  });

  it("falls back to default ports when none survive validation", () => {
    const r = validateSettings({ frontendUrls: ["abc", 0, 99999] });
    expect(r.valid).toBe(false);
    expect(r.errors).toContain("frontendUrls invalide");
    expect(r.settings.frontendUrls).toEqual(DEFAULT_SETTINGS.frontendUrls);
  });

  it("falls back when frontendUrls is not an array", () => {
    const r = validateSettings({ frontendUrls: "5173" });
    expect(r.valid).toBe(false);
    expect(r.settings.frontendUrls).toEqual(DEFAULT_SETTINGS.frontendUrls);
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
    expect(r.settings.frontendUrls).not.toBe(DEFAULT_SETTINGS.frontendUrls);
  });
});

describe("expandFrontendUrls", () => {
  it("derives 127.0.0.1 and localhost URLs from each port", () => {
    expect(expandFrontendUrls([5173, 5174])).toEqual([
      "http://127.0.0.1:5173/",
      "http://localhost:5173/",
      "http://127.0.0.1:5174/",
      "http://localhost:5174/",
    ]);
  });

  it("returns an empty list for an empty port list", () => {
    expect(expandFrontendUrls([])).toEqual([]);
  });
});

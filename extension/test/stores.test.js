import { describe, it, expect } from "vitest";
import { STORES, STORE_KEYS, getStore } from "../lib/stores.js";

describe("stores", () => {
  it("exposes the four supported enseignes", () => {
    expect(Object.keys(STORES).sort()).toEqual([
      "auchan",
      "carrefour",
      "intermarche",
      "leclerc",
    ]);
  });

  it("carries a label, cookie domains and a homepage for every store", () => {
    for (const [key, def] of Object.entries(STORES)) {
      expect(typeof def.label, `${key} label`).toBe("string");
      expect(def.label.length, `${key} label non-empty`).toBeGreaterThan(0);
      expect(Array.isArray(def.cookieDomains), `${key} cookieDomains`).toBe(true);
      expect(def.cookieDomains.length, `${key} has cookie domains`).toBeGreaterThan(0);
      expect(def.cookieDomains.every((d) => typeof d === "string" && d.length > 0)).toBe(true);
      expect(/^https?:\/\//.test(def.homepage), `${key} homepage`).toBe(true);
    }
  });

  it("maps each store to its real session marker cookie", () => {
    expect(STORES.carrefour.sessionMarker).toBe("FRO_CONNECTED");
    expect(STORES.intermarche.sessionMarker).toBe("itm_session");
    expect(STORES.leclerc.sessionMarker).toBe(".XPRSDRVAUTH");
    expect(STORES.auchan.sessionMarker).toBe("lark-session");
  });

  it("keeps the exact carrefour definition", () => {
    expect(STORES.carrefour).toEqual({
      label: "Carrefour",
      cookieDomains: [".carrefour.fr", "www.carrefour.fr"],
      homepage: "https://www.carrefour.fr/",
      sessionMarker: "FRO_CONNECTED",
    });
  });

  it("exposes STORE_KEYS matching the store map", () => {
    expect(STORE_KEYS.sort()).toEqual(Object.keys(STORES).sort());
  });

  it("resolves a known store and rejects unknown keys", () => {
    expect(getStore("auchan")).toBe(STORES.auchan);
    expect(getStore("unknown")).toBeNull();
  });
});

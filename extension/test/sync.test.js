import { describe, it, expect } from "vitest";
import {
  cooldownDurationMs,
  shouldSync,
  normalizeCookie,
  buildPayload,
} from "../lib/sync.js";

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

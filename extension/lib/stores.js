// The four supported enseignes and their connection metadata. Pure data — no
// chrome dependency — so it can be imported by popup.js, the background worker
// and the options page alike.

export const STORES = {
  carrefour: {
    label: "Carrefour",
    cookieDomains: [".carrefour.fr", "www.carrefour.fr"],
    homepage: "https://www.carrefour.fr/",
    sessionMarker: "FRO_CONNECTED",
  },
  intermarche: {
    label: "Intermarché",
    cookieDomains: [".intermarche.com", "www.intermarche.com"],
    homepage: "https://www.intermarche.com/",
    sessionMarker: "itm_session",
  },
  leclerc: {
    label: "Leclerc",
    cookieDomains: [".leclercdrive.fr", "www.leclercdrive.fr"],
    homepage: "https://www.leclercdrive.fr/",
    sessionMarker: ".XPRSDRVAUTH",
  },
  auchan: {
    label: "Auchan",
    cookieDomains: [".auchan.fr", "www.auchan.fr"],
    homepage: "https://www.auchan.fr/",
    sessionMarker: "lark-session",
  },
};

export const STORE_KEYS = Object.keys(STORES);

export function getStore(key) {
  return STORES[key] ?? null;
}

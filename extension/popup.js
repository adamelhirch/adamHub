// Hard-coded for now — TODO: make configurable once the hub has a stable URL.
const HUB_URL = "http://127.0.0.1:8000";
const FRONTEND_URLS = ["http://127.0.0.1:5173/", "http://localhost:5173/"];
const TOKEN_LOCALSTORAGE_KEY = "adamhub_token";

const STORES = {
  carrefour: {
    label: "Carrefour",
    cookieDomains: [".carrefour.fr", "www.carrefour.fr"],
    homepage: "https://www.carrefour.fr/",
    sessionMarker: "FRONTONE_CONNECTED",
  },
  intermarche: {
    label: "Intermarché",
    cookieDomains: [".intermarche.com", "www.intermarche.com"],
    homepage: "https://www.intermarche.com/",
    sessionMarker: null,
  },
  leclerc: {
    label: "Leclerc",
    cookieDomains: [".leclercdrive.fr", "www.leclercdrive.fr"],
    homepage: "https://www.leclercdrive.fr/",
    sessionMarker: null,
  },
  auchan: {
    label: "Auchan",
    cookieDomains: [".auchan.fr", "www.auchan.fr"],
    homepage: "https://www.auchan.fr/",
    sessionMarker: null,
  },
};

const $ = (sel) => document.querySelector(sel);
const statusEl = $("#status");
const authPrompt = $("#auth-prompt");
const accountBadge = $("#account-badge");

function showStatus(kind, message) {
  statusEl.className = `status ${kind}`;
  statusEl.textContent = message;
  statusEl.classList.remove("hidden");
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function showAuthPrompt(show) {
  authPrompt.classList.toggle("hidden", !show);
}

async function findHubTabs() {
  // Look for a logged-in AdamHUB frontend tab to read the JWT from.
  const tabs = await chrome.tabs.query({});
  return tabs.filter((tab) => {
    if (!tab.url) return false;
    return FRONTEND_URLS.some((u) => tab.url.startsWith(u.replace(/\/$/, "")));
  });
}

async function readTokenFromTab(tabId) {
  try {
    const results = await chrome.scripting.executeScript({
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
    return results[0]?.result || null;
  } catch (err) {
    console.warn("[AdamHUB] readTokenFromTab failed:", err);
    return null;
  }
}

async function getAuthToken() {
  // First check our own storage (cached from last successful sync).
  const cached = await chrome.storage.local.get(["token"]);
  if (cached.token) {
    return { token: cached.token, source: "cache" };
  }
  // Fall back to scanning open AdamHUB tabs.
  const tabs = await findHubTabs();
  for (const tab of tabs) {
    const token = await readTokenFromTab(tab.id);
    if (token) {
      await chrome.storage.local.set({ token });
      return { token, source: "tab" };
    }
  }
  return { token: null, source: null };
}

async function fetchAccount(token) {
  try {
    const response = await fetch(`${HUB_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

async function readCookiesForStore(storeKey) {
  const def = STORES[storeKey];
  const cookies = [];
  const seen = new Set();
  for (const domain of def.cookieDomains) {
    const list = await chrome.cookies.getAll({ domain });
    for (const cookie of list) {
      const fp = `${cookie.name}|${cookie.domain}|${cookie.path}`;
      if (seen.has(fp)) continue;
      seen.add(fp);
      const out = {
        name: cookie.name,
        value: cookie.value,
        domain: cookie.domain,
        path: cookie.path,
        secure: !!cookie.secure,
        httpOnly: !!cookie.httpOnly,
      };
      if (cookie.sameSite) {
        const map = { lax: "Lax", strict: "Strict", no_restriction: "None", none: "None" };
        out.sameSite = map[cookie.sameSite] ?? cookie.sameSite;
      }
      if (cookie.expirationDate) {
        out.expires = Math.round(cookie.expirationDate);
      }
      cookies.push(out);
    }
  }
  return cookies;
}

async function postCookies(storeKey, cookies, token) {
  const response = await fetch(`${HUB_URL}/api/v1/supermarket/connections/import`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      store: storeKey,
      label: "",
      cookies,
      activate: true,
    }),
  });
  if (response.status === 401) {
    // Token expired or invalid — clear cache so we re-read from a tab.
    await chrome.storage.local.remove("token");
    throw new Error("Session expirée. Reconnecte-toi sur AdamHUB puis recommence.");
  }
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      detail = await response.text();
    }
    throw new Error(`HTTP ${response.status} — ${detail || "erreur inconnue"}`);
  }
  return response.json();
}

async function refreshConnectionStatus() {
  const stored = await chrome.storage.local.get(["lastSync"]);
  const lastSync = stored.lastSync || {};
  for (const key of Object.keys(STORES)) {
    const meta = document.getElementById(`meta-${key}`);
    if (!meta) continue;
    const stamp = lastSync[key];
    if (stamp) {
      const date = new Date(stamp);
      meta.textContent = `synchronisé le ${date.toLocaleDateString("fr-FR")} à ${date.toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      })}`;
      meta.classList.add("connected");
    } else {
      meta.textContent = "non connecté";
      meta.classList.remove("connected");
    }
  }
}

async function refreshAccountBadge() {
  try {
    const { token } = await getAuthToken();
    if (!token) {
      accountBadge.classList.add("hidden");
      showAuthPrompt(true);
      return false;
    }
    const account = await fetchAccount(token);
    if (!account) {
      accountBadge.classList.add("hidden");
      showAuthPrompt(true);
      await chrome.storage.local.remove("token");
      return false;
    }
    accountBadge.textContent = account.display_name;
    accountBadge.classList.remove("hidden");
    showAuthPrompt(false);
    return true;
  } catch (err) {
    console.warn("[AdamHUB] refreshAccountBadge failed:", err);
    accountBadge.classList.add("hidden");
    showAuthPrompt(true);
    return false;
  }
}

async function connectStore(storeKey) {
  hideStatus();
  const def = STORES[storeKey];
  const button = document.querySelector(`button[data-store="${storeKey}"]`);
  if (button) {
    button.disabled = true;
    button.textContent = "Lecture…";
  }
  try {
    const { token } = await getAuthToken();
    if (!token) {
      throw new Error(
        "Connecte-toi à AdamHUB d'abord (clique « Ouvrir AdamHUB » au-dessus).",
      );
    }
    const cookies = await readCookiesForStore(storeKey);
    if (cookies.length === 0) {
      throw new Error(
        `Aucun cookie ${def.label} trouvé. Connecte-toi sur ${def.homepage} dans cet onglet, puis recommence.`,
      );
    }
    if (def.sessionMarker && !cookies.some((c) => c.name === def.sessionMarker)) {
      throw new Error(
        `Pas de session ${def.label} active (cookie ${def.sessionMarker} manquant). Connecte-toi puis recommence.`,
      );
    }
    if (button) button.textContent = "Envoi au hub…";
    const result = await postCookies(storeKey, cookies, token);

    const stored = await chrome.storage.local.get(["lastSync"]);
    const lastSync = { ...(stored.lastSync || {}), [storeKey]: Date.now() };
    await chrome.storage.local.set({ lastSync });

    const count = result?.cookies_count ?? cookies.length;
    showStatus(
      "success",
      `✓ ${def.label} synchronisé (${count} cookies, étiquette « ${result?.label || "?"} »).`,
    );
  } catch (error) {
    showStatus("error", `✗ ${error.message ?? error}`);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Connecter";
    }
    refreshConnectionStatus();
  }
}

function bindEventListeners() {
  // Always bind FIRST so the popup is interactive even if async init fails.
  const openHubBtn = $("#open-hub");
  if (openHubBtn) {
    openHubBtn.addEventListener("click", async () => {
      try {
        await chrome.tabs.create({ url: FRONTEND_URLS[0] });
      } catch (err) {
        showStatus("error", `Impossible d'ouvrir AdamHUB : ${err.message ?? err}`);
      }
    });
  }
  for (const button of document.querySelectorAll('button[data-action="connect"]')) {
    button.addEventListener("click", () => {
      void connectStore(button.dataset.store);
    });
  }
  console.log("[AdamHUB] event listeners bound");
}

async function init() {
  bindEventListeners();
  let ok = false;
  try {
    ok = await refreshAccountBadge();
  } catch (err) {
    console.warn("[AdamHUB] init refreshAccountBadge:", err);
  }
  try {
    await refreshConnectionStatus();
  } catch (err) {
    console.warn("[AdamHUB] init refreshConnectionStatus:", err);
  }
  if (!ok) {
    showStatus("info", "Ouvre AdamHUB dans un onglet et connecte-toi pour démarrer.");
  }
}

init();

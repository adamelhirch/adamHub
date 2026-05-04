// Service worker — currently minimal. Reserved for future automatic re-sync
// (e.g. detect 401 from the hub and prompt the user to re-login).

self.addEventListener("install", () => {
  // Skip waiting so updates take effect immediately on reload.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

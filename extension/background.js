// MV3 module service worker — thin wiring. All logic lives in lib/worker.js so
// it can be unit-tested without a browser; this file only registers the chrome
// event listeners and delegates to the injected worker.

import { createWorker } from "./lib/worker.js";

const worker = createWorker({ chrome });

// Take control of existing tabs immediately after install/update.
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// Install / update → (re)schedule the periodic alarm; on a fresh install also
// attempt an immediate sync (or prompt a reconnect when no token is cached).
chrome.runtime.onInstalled.addListener((details) => {
  void worker.handleInstalled(details);
});

// Browser restart → restore the periodic alarm.
chrome.runtime.onStartup.addListener(() => {
  void worker.handleStartup();
});

// Periodic alarm → sync every enabled store.
chrome.alarms.onAlarm.addListener((alarm) => {
  void worker.handleAlarm(alarm);
});

// Store tab finished loading → sync that store (respecting its cooldown).
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  void worker.handleTabUpdated(tabId, changeInfo, tab);
});

// Reconnect/error notification clicked → open the hub when appropriate.
chrome.notifications.onClicked.addListener((id) => {
  void worker.handleNotificationClicked(id);
});

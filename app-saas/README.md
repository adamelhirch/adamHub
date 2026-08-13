# app-saas — Mobile-first SaaS frontend

Brand-new mobile-first frontend for a separate SaaS product built on a subset of
the existing AdamHUB backend (recipes / meal-plans / groceries / pantry /
supermarket). Distinct from the legacy `web/` frontend — same backend, own
branding (working name: "AdamHUB SaaS").

Stack: Expo SDK 57 + Expo Router (file-based routing) + TypeScript + NativeWind
(Tailwind syntax for React Native). Runs on iOS, Android and web from one
codebase (react-native-web).

## Prerequisites

- Node.js (current LTS, e.g. 22+)
- For iOS simulator: Xcode
- For Android emulator: Android Studio + an AVD
- The AdamHUB backend running locally at `http://localhost:8000` (see the repo
  root `README.md` / `docker-compose.yml`)

## Install

```bash
cd app-saas
npm install
```

## Environment

Copy `.env.example` to `.env` and adjust if your backend is not on localhost:

```bash
cp .env.example .env
```

| Var | Default | Description |
| --- | --- | --- |
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Base URL of the backend API. Prefix `EXPO_PUBLIC_` is required for Expo to inline the value into the bundle. |

## Run

```bash
npx expo start
```

Then press the matching key in the terminal, or use one of:

| Platform | Command | Notes |
| --- | --- | --- |
| iOS simulator | `npx expo start --ios` | Requires Xcode simulator |
| Android emulator | `npx expo start --android` | Requires a running AVD |
| Web | `npx expo start --web` | Opens `http://localhost:8081` |

You can also open the project in the Expo Go app on a physical device by
scanning the QR code shown by `npx expo start`.

## What's implemented (scaffold)

- **Auth flow** — `/login` and `/register` screens calling the real backend
  endpoints `POST /api/v1/auth/login` and `POST /api/v1/auth/register`. The
  returned JWT is stored in `expo-secure-store` on iOS/Android, with a
  `localStorage` fallback on web (SecureStore is not available there).
- **Root redirect** — `/` checks for a stored token and routes to the app shell
  or the auth flow.
- **App shell** — bottom tabs with three placeholder screens fed by mock data:
  `Repas` (weekly meal plan), `Courses` (grocery list), `Garde-manger`
  (pantry). No real data fetching yet; mock data lives in `src/data/mock.ts`
  with typed structures so real API calls can replace it later.

## Structure

```
app-saas/
├── app.json                  # Expo config (name, scheme, web bundler)
├── babel.config.js           # Babel: expo preset + NativeWind
├── metro.config.js           # Metro: NativeWind CSS input
├── tailwind.config.js        # Tailwind content paths + NativeWind preset
├── nativewind-env.d.ts       # NativeWind type definitions
├── src/
│   ├── global.css            # Tailwind directives (NativeWind input)
│   ├── app/                  # Expo Router routes
│   │   ├── _layout.tsx       # Root Stack layout
│   │   ├── index.tsx         # Token check → redirect (auth vs shell)
│   │   ├── (auth)/           # login / register screens
│   │   └── (tabs)/           # bottom-tab shell: Repas / Courses / Garde-manger
│   ├── components/           # Reusable UI (Screen, Field, Button, header)
│   ├── data/mock.ts          # Typed mock data for the tab screens
│   └── lib/
│       ├── api.ts            # Fetch client + login/register + JWT handling
│       └── token-storage.ts  # SecureStore (native) / localStorage (web)
└── .env.example              # EXPO_PUBLIC_API_URL
```

## Typecheck / lint

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # expo lint
```

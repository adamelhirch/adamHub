# Uber Eats grocery scraping

This module lets the hub list Uber Eats grocery stores at a given delivery
address, persist a chosen store, and run product searches against it.

## Setup

1. **Export cookies** from a logged-in Uber Eats browser session into
   `data/cookies_ubereats.json`. Use the same Chrome extension format as
   `cookies_intermarche.json` (an array of `{name, value, domain, ...}`
   objects). The file is gitignored.

   The minimum cookies that matter:
   - `sid`, `csid`, `jwt-session` — auth
   - `uev2.id.session`, `uev2.id.xp` — Uber Eats session identifiers
   - `uev2.loc` — current delivery location (URL-encoded JSON)

2. **Optional residential proxy** via `ADAMHUB_UBEREATS_PROXY_URL`
   (`http://user:pass@host:port`).

## Default address

The address comes from the `uev2.loc` cookie. `GET /supermarket/ubereats/location`
returns the decoded `{title, formatted_address, latitude, longitude}` so you
can confirm what the session is going to use.

## Changing the address

```http
PUT /supermarket/ubereats/location
{
  "title": "Bureau",
  "subtitle": "Paris 11e",
  "formatted_address": "23 rue de la Roquette, 75011 Paris",
  "latitude": 48.8566,
  "longitude": 2.3522,
  "reference": "ChIJ...",
  "reference_type": "GOOGLE_PLACES"
}
```

This rewrites the `uev2.loc` cookie in `data/cookies_ubereats.json`.
`reference` is optional — supply the Google Place ID if you have it,
otherwise Uber Eats falls back to lat/lng resolution.

## Picking a store

```http
GET  /supermarket/ubereats/stores?limit=25
PUT  /supermarket/ubereats/selected-store
     { "external_store_id": "<uuid>", "store_label": "Carrefour City — Roquette" }
GET  /supermarket/ubereats/selected-store
```

`GET /stores` calls `getFeedV1` filtered on `GROCERY` and returns only
grocery / convenience venues at the current address.

## Searching

Once a store is selected, the existing search endpoint dispatches to it:

```http
POST /supermarket/search
     { "store": "ubereats", "queries": ["banane bio", "lait demi-écrémé"], "max_results": 10 }
```

Results land in the same `SupermarketSearchCache` table as Intermarché
(15-day TTL, deduped by `external_id`).

## Errors you may hit

| Status | Meaning |
| ------ | ------- |
| `401`  | Cookies missing or rejected — re-export `cookies_ubereats.json` |
| `409`  | No `uev2.loc` set — call `PUT /ubereats/location` or re-export cookies |
| `503`  | Uber Eats returned an unexpected response (retry, or check the API has not changed shape) |

## Notes

- The internal API endpoints are not officially documented and can shift.
  Parsing is intentionally tolerant (walks the JSON tree) and only requires
  a `uuid` + `title` + a price field per item.
- Cart automation is intentionally out of scope. The agent surfaces
  prices/quantities; the user adds to cart and checks out manually.

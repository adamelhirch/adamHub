# Contract: Supermarket Store Locator & Preferences API

**Base Path**: `/api/v1/supermarket/stores`
**Authentication**: Header `Authorization: Bearer <JWT>` ou `X-API-Key: <key>` (`CurrentOrOwnerUser`)

---

## 1. Recherche de Magasins et Points de Retrait

### `GET /api/v1/supermarket/stores/search`
Recherche les points de retrait drive pour une ou toutes les enseignes supportées autour d'une ville ou d'un code postal.

#### Query Parameters
| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `store` | `SupermarketStore` | Optionnel | `leclerc`, `auchan`, `carrefour`, `intermarche` (si omis, recherche globale) |
| `zipcode` | `str` | Optionnel | Code postal français (ex. `31700`) |
| `city` | `str` | Optionnel | Nom de commune (ex. `Blagnac`) |
| `latitude` | `float` | Optionnel | Coordonnée GPS latitude |
| `longitude` | `float` | Optionnel | Coordonnée GPS longitude |

#### Response 200 OK
```json
[
  {
    "store": "leclerc",
    "external_store_id": "0123",
    "name": "E.Leclerc Drive Blagnac",
    "address": "Zone Commerciale du Grand Noble",
    "zipcode": "31700",
    "city": "Blagnac",
    "pickup_type": "quai",
    "distance_km": 2.4,
    "channel": "drive"
  },
  {
    "store": "leclerc",
    "external_store_id": "0123_TAPE_1",
    "name": "Borne TAPE Leclerc Cornebarrieu",
    "address": "Route de Colomiers",
    "zipcode": "31700",
    "city": "Cornebarrieu",
    "pickup_type": "tape",
    "distance_km": 4.8,
    "channel": "tape"
  },
  {
    "store": "auchan",
    "external_store_id": "seller_987",
    "name": "Auchan Drive Toulouse Balma",
    "address": "Route de Castres",
    "zipcode": "31130",
    "city": "Balma",
    "pickup_type": "quai",
    "distance_km": 5.1,
    "channel": "drive"
  }
]
```

---

## 2. Consultation des Préférences Magasins de l'Utilisateur

### `GET /api/v1/supermarket/stores/preferences`
Retourne la configuration des magasins favoris de l'utilisateur connecté pour chaque enseigne.

#### Response 200 OK
```json
[
  {
    "store": "leclerc",
    "external_store_id": "0123",
    "store_label": "E.Leclerc Drive Blagnac",
    "location_label": "Zone Commerciale du Grand Noble, 31700 Blagnac",
    "pickup_type": "quai",
    "optimization_strategy": "mdd",
    "updated_at": "2026-09-13T10:00:00Z"
  }
]
```

---

## 3. Définition / Modification du Magasin Favori

### `PUT /api/v1/supermarket/stores/preferences/{store}`
Définit ou met à jour le magasin drive favori pour une enseigne donnée.

#### Request Body
```json
{
  "external_store_id": "0123_TAPE_1",
  "store_label": "Borne TAPE Leclerc Cornebarrieu",
  "location_label": "Route de Colomiers, 31700 Cornebarrieu",
  "pickup_type": "tape",
  "optimization_strategy": "mdd",
  "channel": "tape",
  "raw_context": {}
}
```

#### Response 200 OK
```json
{
  "store": "leclerc",
  "external_store_id": "0123_TAPE_1",
  "store_label": "Borne TAPE Leclerc Cornebarrieu",
  "location_label": "Route de Colomiers, 31700 Cornebarrieu",
  "pickup_type": "tape",
  "optimization_strategy": "mdd",
  "updated_at": "2026-09-13T12:00:00Z"
}
```

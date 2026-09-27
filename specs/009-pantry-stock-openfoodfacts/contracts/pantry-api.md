# Pantry & Open Food Facts API Contracts

**Feature**: `009-pantry-stock-openfoodfacts`  
**Date**: 2026-09-15  
**Status**: Completed  

---

## 1. Open Food Facts Barcode Lookup

### `GET /api/v1/pantry/barcode/{barcode}`

Looks up a product by its EAN/UPC barcode in local cache or Open Food Facts, applying intelligent name cleaning and metric normalization.

#### Path Parameters
- `barcode` (string, required): EAN-13, EAN-8, or UPC barcode (e.g. `3017620422003`, `3560070557451`).

#### Success Response: `200 OK` (Product Found)
```json
{
  "barcode": "3560070557451",
  "found": true,
  "raw_name": "Carrefour Extra Penne Rigate 500g",
  "brand": "Carrefour Extra",
  "suggested_name": "Pâtes penne",
  "quantity": 500.0,
  "unit": "g",
  "category": "Épicerie",
  "image_url": "https://images.openfoodfacts.org/images/products/356/007/055/7451/front_fr.jpg",
  "nutriscore": "a",
  "packaging": "Paquet carton 500 g",
  "location": "Placard",
  "missing_fields": ["expires_at"]
}
```

#### Success Response: `200 OK` (Product Not Found)
```json
{
  "barcode": "9999999999999",
  "found": false,
  "raw_name": null,
  "brand": null,
  "suggested_name": "",
  "quantity": 1.0,
  "unit": "item",
  "category": null,
  "image_url": null,
  "nutriscore": null,
  "packaging": null,
  "location": "Placard",
  "missing_fields": ["name", "quantity", "unit", "category", "expires_at"]
}
```

#### Error Responses
- `400 Bad Request`: Invalid barcode format.
- `503 Service Unavailable`: Open Food Facts network timeout (with fallback suggestion for manual entry).

---

## 2. Direct Pantry Item Modification

### `PATCH /api/v1/pantry/items/{item_id}`

Updates any attributes of an existing pantry item owned by the acting user.

#### Path Parameters
- `item_id` (integer, required): ID of the pantry item.

#### Request Body (`application/json`)
```json
{
  "name": "Saumon frais",
  "quantity": 300.0,
  "unit": "g",
  "category": "Poisson",
  "location": "Réfrigérateur",
  "min_quantity": 100.0,
  "expires_at": "2026-09-20",
  "note": "2 pavés"
}
```

#### Success Response: `200 OK`
```json
{
  "id": 7,
  "name": "Saumon frais",
  "quantity": 300.0,
  "unit": "g",
  "category": "Poisson",
  "image_url": null,
  "store_label": null,
  "external_id": null,
  "packaging": null,
  "price_text": null,
  "product_url": null,
  "min_quantity": 100.0,
  "expires_at": "2026-09-20",
  "location": "Réfrigérateur",
  "note": "2 pavés",
  "created_at": "2026-09-05T19:18:44Z",
  "updated_at": "2026-09-15T15:30:00Z"
}
```

#### Error Responses
- `404 Not Found`: Item does not exist or belongs to another tenant (Constitution Principle I).
- `422 Unprocessable Entity`: Negative quantity or invalid date format.

---

## 3. Pantry Item Creation from Barcode or Manual Entry

### `POST /api/v1/pantry/items`

Creates a new item in the user's pantry.

#### Request Body (`application/json`)
```json
{
  "name": "Pâtes penne",
  "quantity": 500.0,
  "unit": "g",
  "category": "Épicerie",
  "store_label": "Carrefour Extra",
  "external_id": "3560070557451",
  "location": "Placard",
  "expires_at": "2027-06-01",
  "image_url": "https://images.openfoodfacts.org/images/products/...",
  "note": "Acheté au drive"
}
```

#### Success Response: `200 OK`
Returns the created `PantryItemRead` object.

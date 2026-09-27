# REST API Contract: Supermarket Carts

Base Path: `/api/v1/supermarket/carts`
Authentication: Bearer JWT (`CurrentOrOwnerUser`) or `X-API-Key` (Owner).

---

### 1. List Carts
- **Endpoint**: `GET /api/v1/supermarket/carts`
- **Description**: Returns all supermarket carts for the authenticated user across stores.
- **Response**: `200 OK`
  ```json
  [
    {
      "id": 1,
      "store": "intermarche",
      "status": "draft",
      "created_at": "2026-09-11T12:00:00Z",
      "updated_at": "2026-09-11T12:05:00Z",
      "total_amount": 14.50,
      "items_count": 3,
      "items": [...]
    },
    {
      "id": 2,
      "store": "carrefour",
      "status": "draft",
      "created_at": "2026-09-11T12:00:00Z",
      "updated_at": "2026-09-11T12:10:00Z",
      "total_amount": 22.80,
      "items_count": 5,
      "items": [...]
    }
  ]
  ```

---

### 2. Get Store Cart (Live Mirror)
- **Endpoint**: `GET /api/v1/supermarket/carts/{store}`
- **Path Parameters**:
  - `store`: `intermarche | carrefour | leclerc | auchan`
- **Description**: Re-reads the remote retailer cart in real time and updates the local mirror.
- **Response**: `200 OK`
  ```json
  {
    "id": 1,
    "store": "carrefour",
    "status": "draft",
    "created_at": "2026-09-11T12:00:00Z",
    "updated_at": "2026-09-11T12:05:00Z",
    "total_amount": 18.20,
    "items_count": 2,
    "items": [
      {
        "id": 10,
        "external_id": "32452",
        "name": "Lait demi-écrémé 1L",
        "quantity": 2,
        "price_amount": 1.10,
        "price_text": "1.10 €",
        "image_url": "https://cdn.example.com/img.jpg"
      }
    ]
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Missing active connection, unselected store Drive/location, or missing customer context.
  - `401 Unauthorized`: Store session expired or invalidated by retailer.
  - `503 Service Unavailable`: Retailer temporarily unreachable or blocked by anti-bot challenge.

---

### 3. Add Item to Cart
- **Endpoint**: `POST /api/v1/supermarket/carts/{store}/items`
- **Body**:
  ```json
  {
    "cache_id": 42,
    "quantity": 2
  }
  ```
- **Description**: Resolves verified store catalog metadata from `SupermarketSearchCache` and adds the item to the remote retailer cart, reconciling the local cart mirror.
- **Response**: `200 OK` (returns updated `SupermarketCartRead`).

---

### 4. Update Item Quantity
- **Endpoint**: `PATCH /api/v1/supermarket/carts/{store}/items/{item_id}`
- **Path Parameters**:
  - `store`: `intermarche | carrefour | leclerc | auchan`
  - `item_id`: ID of the local `SupermarketCartItem`
- **Body**:
  ```json
  {
    "quantity": 3
  }
  ```
- **Description**: Adjusts item quantity on remote retailer cart and mirrors the response. If quantity is 0, removes the item.
- **Response**: `200 OK` (returns updated `SupermarketCartRead`).

---

### 5. Remove Item from Cart
- **Endpoint**: `DELETE /api/v1/supermarket/carts/{store}/items/{item_id}`
- **Description**: Removes the specific line item from the remote retailer cart and reconciles the local mirror.
- **Response**: `200 OK` (returns updated `SupermarketCartRead`).

---

### 6. Clear Entire Cart
- **Endpoint**: `DELETE /api/v1/supermarket/carts/{store}`
- **Description**: Wipes all items from the remote retailer cart and empties the local mirror.
- **Response**: `200 OK` (returns updated `SupermarketCartRead` with 0 items).

# MCP Tool Contracts: Supermarket Carts for AI Agents

These tools are exposed via the Model Context Protocol (MCP) in `app/mcp/server.py` and the skill action catalog in `app/skill/actions.py`, scoped to the acting user.

---

### 1. `supermarket.get_cart`
- **Description**: "Retrieve the current contents, item quantities, prices, and status of a supermarket cart for a given store (Intermarché, Carrefour, Leclerc, Auchan)."
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {
        "type": "string",
        "enum": ["intermarche", "carrefour", "leclerc", "auchan"],
        "description": "Supermarket chain identifier."
      },
      "force_sync": {
        "type": "boolean",
        "description": "Whether to force a live refresh from the remote retailer site.",
        "default": true
      }
    },
    "required": ["store"]
  }
  ```
- **Output Schema**:
  ```json
  {
    "store": "carrefour",
    "status": "draft",
    "total_amount": 14.50,
    "items_count": 2,
    "items": [
      {
        "id": 10,
        "external_id": "32452",
        "name": "Lait demi-écrémé 1L",
        "quantity": 2,
        "price_amount": 1.10,
        "price_text": "1.10 €",
        "image_url": "https://..."
      }
    ]
  }
  ```

---

### 2. `supermarket.list_carts`
- **Description**: "List all active supermarket shopping carts across all supported retailers for the user."
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {}
  }
  ```
- **Output Schema**: Array of cart summary objects.

---

### 3. `supermarket.add_cart_item`
- **Description**: "Add a product from authentic supermarket search results to the store's cart."
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {
        "type": "string",
        "enum": ["intermarche", "carrefour", "leclerc", "auchan"]
      },
      "cache_id": {
        "type": "integer",
        "description": "ID of the cached search result item from supermarket.search."
      },
      "quantity": {
        "type": "integer",
        "description": "Quantity to add (minimum 1).",
        "default": 1
      }
    },
    "required": ["store", "cache_id"]
  }
  ```

---

### 4. `supermarket.update_cart_item`
- **Description**: "Update the quantity of an existing line item in a store's cart."
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {
        "type": "string",
        "enum": ["intermarche", "carrefour", "leclerc", "auchan"]
      },
      "item_id": {
        "type": "integer",
        "description": "The cart line item ID."
      },
      "quantity": {
        "type": "integer",
        "description": "Target quantity (0 removes the item)."
      }
    },
    "required": ["store", "item_id", "quantity"]
  }
  ```

---

### 5. `supermarket.remove_cart_item`
- **Description**: "Remove an individual product line from a supermarket cart."
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {
        "type": "string",
        "enum": ["intermarche", "carrefour", "leclerc", "auchan"]
      },
      "item_id": {
        "type": "integer",
        "description": "The cart line item ID."
      }
    },
    "required": ["store", "item_id"]
  }
  ```

---

### 6. `supermarket.clear_cart`
- **Description**: "Empty the user's shopping cart for a specific supermarket retailer."
- **Input Schema**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {
        "type": "string",
        "enum": ["intermarche", "carrefour", "leclerc", "auchan"]
      }
    },
    "required": ["store"]
  }
  ```

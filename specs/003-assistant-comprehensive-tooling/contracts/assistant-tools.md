# Assistant Tool Contracts: Comprehensive Tooling & Smart Scheduling

All functions are exposed to the conversational LLM in OpenAI function-calling format (where periods in action names are replaced by double underscores, e.g. `recipe.add` -> `recipe__add`), strictly scoped to the authenticated user.

---

## 1. Recipe Management Tools

### `recipe__add`
- **Description**: "Create a new structured recipe with discrete ingredients, instructions, and preparation metadata. NEVER use tasks for culinary recipes."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "name": {"type": "string", "description": "Recipe title, e.g. Risotto aux champignons"},
      "description": {"type": "string", "description": "Short culinary summary"},
      "instructions": {"type": "string", "description": "Full cooking instructions or general steps"},
      "steps": {"type": "array", "items": {"type": "string"}, "description": "Discrete cooking steps"},
      "utensils": {"type": "array", "items": {"type": "string"}, "description": "Required utensils"},
      "prep_minutes": {"type": "integer", "description": "Preparation duration in minutes"},
      "cook_minutes": {"type": "integer", "description": "Cooking duration in minutes"},
      "servings": {"type": "integer", "description": "Yield in number of persons (default 1)"},
      "tags": {"type": "array", "items": {"type": "string"}, "description": "Culinary tags e.g. italien, rapide"},
      "ingredients": {
        "type": "array",
        "description": "Structured ingredient lines",
        "items": {
          "type": "object",
          "properties": {
            "name": {"type": "string"},
            "quantity": {"type": "number"},
            "unit": {"type": "string"},
            "category": {"type": "string"},
            "note": {"type": "string"},
            "cache_id": {"type": "integer"}
          },
          "required": ["name"]
        }
      }
    },
    "required": ["name", "instructions"]
  }
  ```

### `recipe__list`
- **Description**: "List user recipes with search, filtering by duration, tags, or ingredients."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Search term for recipe name or ingredients"},
      "tag": {"type": "string", "description": "Filter by tag"},
      "max_minutes": {"type": "integer", "description": "Filter by maximum total time (prep + cook)"},
      "limit": {"type": "integer", "default": 20}
    }
  }
  ```

### `recipe__get`
- **Description**: "Retrieve full recipe details including structured ingredients, utensils, and steps."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "recipe_id": {"type": "integer", "description": "ID of the recipe to view"}
    },
    "required": ["recipe_id"]
  }
  ```

### `recipe__update`
- **Description**: "Update an existing recipe's fields, steps, servings, or ingredient items."
- **Parameters**: Same fields as `recipe__add` plus `recipe_id` (required).

### `recipe__delete`
- **Description**: "Delete a recipe. MUST only be called after explicit user confirmation."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "recipe_id": {"type": "integer"}
    },
    "required": ["recipe_id"]
  }
  ```

---

## 2. Smart Calendar & Conflict Resolution Tools

### `calendar__add_item`
- **Description**: "Schedule an event on the user timeline. Validates against collisions. If a collision is found and force is false, returns conflicting events and suggested alternative slots without saving."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "title": {"type": "string", "description": "Event title"},
      "start_at": {"type": "string", "description": "Start timestamp in ISO 8601 UTC"},
      "end_at": {"type": "string", "description": "End timestamp in ISO 8601 UTC"},
      "category": {"type": "string", "enum": ["general", "task", "meal", "fitness", "event"], "default": "general"},
      "description": {"type": "string"},
      "force": {"type": "boolean", "description": "If true, bypass collision rejection and schedule despite overlap", "default": false}
    },
    "required": ["title", "start_at", "end_at"]
  }
  ```
- **Returns on Conflict (`force=false`)**:
  ```json
  {
    "conflict": true,
    "message": "Créneau occupé par un ou plusieurs événements existants.",
    "colliding_items": [
      {
        "title": "Dentiste",
        "start_at": "2026-09-13T10:30:00Z",
        "end_at": "2026-09-13T11:30:00Z"
      }
    ],
    "suggested_slots": [
      {
        "start_at": "2026-09-13T11:30:00Z",
        "end_at": "2026-09-13T12:30:00Z",
        "label": "Immédiatement après le conflit"
      },
      {
        "start_at": "2026-09-13T09:00:00Z",
        "end_at": "2026-09-13T10:00:00Z",
        "label": "Avant le conflit le même jour"
      }
    ]
  }
  ```

### `calendar__check_availability`
- **Description**: "Check if a specific time window is free or retrieve the next open slots of a given duration."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "start_at": {"type": "string", "description": "Candidate start in ISO 8601 UTC"},
      "end_at": {"type": "string", "description": "Candidate end in ISO 8601 UTC"},
      "target_date": {"type": "string", "description": "Date YYYY-MM-DD to search open slots in"},
      "duration_minutes": {"type": "integer", "default": 60}
    }
  }
  ```

---

## 3. Supermarket Drive Tools

### `supermarket__search`
- **Description**: "Search authentic retailer grocery products from supported drive stores (intermarche, carrefour, leclerc, auchan)."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {"type": "string", "enum": ["intermarche", "carrefour", "leclerc", "auchan"]},
      "queries": {"type": "array", "items": {"type": "string"}},
      "max_results": {"type": "integer", "default": 5}
    },
    "required": ["queries"]
  }
  ```

### `supermarket__get_cart`
- **Description**: "Retrieve live shopping cart contents, line item quantities, and total for a supermarket retailer."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {"type": "string", "enum": ["intermarche", "carrefour", "leclerc", "auchan"]},
      "force_sync": {"type": "boolean", "default": true}
    },
    "required": ["store"]
  }
  ```

### `supermarket__add_cart_item`
- **Description**: "Add an authentic product from search results (cache_id) to the supermarket drive cart."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "store": {"type": "string", "enum": ["intermarche", "carrefour", "leclerc", "auchan"]},
      "cache_id": {"type": "integer", "description": "Authentic search cache ID from supermarket__search"},
      "quantity": {"type": "integer", "default": 1}
    },
    "required": ["store", "cache_id"]
  }
  ```

### `supermarket__update_cart_item` / `supermarket__remove_cart_item`
- **Description**: Update quantity or remove item by `item_id` in the store cart.

---

## 4. Meal Planning & Cook Confirmation Tools

### `meal_plan__add`
- **Description**: "Schedule a recipe or meal onto the meal plan. Automatically verifies pantry stock and adds missing ingredients to the grocery list when auto_add_missing_ingredients is true."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "recipe_id": {"type": "integer"},
      "planned_at": {"type": "string", "description": "UTC ISO 8601 timestamp"},
      "slot": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
      "servings_override": {"type": "integer"},
      "auto_add_missing_ingredients": {"type": "boolean", "default": true}
    },
    "required": ["recipe_id"]
  }
  ```

### `recipe__confirm_cooked` / `recipe__unconfirm_cooked`
- **Description**: "Confirm cooking a recipe (decrements pantry stock proportionally) or undo confirmation (restores exact pantry stock)."
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "recipe_id": {"type": "integer"},
      "servings_override": {"type": "integer"},
      "note": {"type": "string"}
    },
    "required": ["recipe_id"]
  }
  ```

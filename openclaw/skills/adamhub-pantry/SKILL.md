# AdamHUB Pantry Skill

Use for inventory management and stock control.

## Actions

- `pantry.add_item`
- `pantry.list_items`
- `pantry.update_item`
- `pantry.consume_item`
- `pantry.overview`

## Rules

- Use `pantry.overview` before shopping recommendations.
- Never reduce quantities below zero (API already guards this).

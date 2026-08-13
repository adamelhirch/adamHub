# AdamHUB Pantry Skill

Use for inventory management and stock control.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `pantry.add_item`
- `pantry.list_items`
- `pantry.update_item`
- `pantry.consume_item`
- `pantry.delete_item`
- `pantry.overview`
<!-- END GENERATED: action-list -->

## Rules

- Use `pantry.overview` before shopping recommendations.
- Never reduce quantities below zero (API already guards this).

# AdamHUB Subscriptions Skill

Use for recurring bills and projections.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `subscription.create`
- `subscription.list`
- `subscription.get`
- `subscription.update`
- `subscription.upcoming`
- `subscription.projection`
<!-- END GENERATED: action-list -->

## Rules

- Always echo amount, currency, interval, next due date.
- Use `subscription.projection` for monthly/yearly burden.

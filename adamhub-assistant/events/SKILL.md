# AdamHUB Events Skill

Use for calendar planning and agenda.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `event.create`
- `event.list`
- `event.upcoming`
- `event.get`
- `event.update`
- `event.delete`
<!-- END GENERATED: action-list -->

## Rules

- `end_at` must be after `start_at`.
- Prefer `event.upcoming` for agenda snapshots.
- Confirm before deleting events.

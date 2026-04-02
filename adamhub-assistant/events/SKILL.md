# AdamHUB Events Skill

Use for calendar planning and agenda.

## Actions

- `event.create`
- `event.list`
- `event.upcoming`
- `event.get`
- `event.update`
- `event.delete`

## Rules

- `end_at` must be after `start_at`.
- Prefer `event.upcoming` for agenda snapshots.
- Confirm before deleting events.

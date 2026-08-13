# AdamHUB Goals Skill

Use for goals and milestones.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `goal.create`
- `goal.list`
- `goal.get`
- `goal.update`
- `goal.add_milestone`
- `goal.list_milestones`
- `goal.update_milestone`
<!-- END GENERATED: action-list -->

## Rules

- If goal id is missing, call `goal.list` first.
- Track progress with `goal.update` (`progress_percent`, `status`).
- Use milestones for medium/long goals.

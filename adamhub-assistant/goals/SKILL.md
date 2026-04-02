# AdamHUB Goals Skill

Use for goals and milestones.

## Actions

- `goal.create`
- `goal.list`
- `goal.get`
- `goal.update`
- `goal.add_milestone`
- `goal.list_milestones`
- `goal.update_milestone`

## Rules

- If goal id is missing, call `goal.list` first.
- Track progress with `goal.update` (`progress_percent`, `status`).
- Use milestones for medium/long goals.

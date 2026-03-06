# AdamHUB Habits Skill

Use for creating habits, tracking logs, and active state management.

## Actions

- `habit.create`
- `habit.list`
- `habit.set_active`
- `habit.log`
- `habit.list_logs`

## Decision rules

- New routine -> `habit.create`
- Show active habits -> `habit.list` with `active_only=true`
- Track completion -> `habit.log`
- Pause/reactivate -> `habit.set_active`
- Audit history -> `habit.list_logs`

## Safety

- Confirm before `habit.set_active` with `active=false`.
- If `habit_id` unknown, call `habit.list` first.
- After `habit.log`, always show updated streak.

# AdamHUB Habits Skill

Use for creating habits, tracking logs, and active state management.

This is the correct skill behind the frontend `Routine` tab inside the Tasks page.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `habit.create`
- `habit.list`
- `habit.update`
- `habit.set_active`
- `habit.log`
- `habit.list_logs`
<!-- END GENERATED: action-list -->

## Decision rules

- New routine -> `habit.create`
- Show active habits -> `habit.list` with `active_only=true`
- Track completion -> `habit.log`
- Pause/reactivate -> `habit.set_active`
- Audit history -> `habit.list_logs`
- If the user says "tache recurrente", "routine", or "habitude", treat it as a habit.

## Safety

- Confirm before `habit.set_active` with `active=false`.
- If `habit_id` unknown, call `habit.list` first.
- After `habit.log`, always show updated streak.

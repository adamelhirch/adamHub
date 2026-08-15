# AdamHUB Calendar Skill

Use for manual calendar blocks, day agendas, reminders, and calendar sync.

Every time-based AdamHUB entity (tasks, habits, events, subscriptions, meal plans, fitness sessions) materializes as a calendar item. Prefer the domain-specific skill for creating or updating those source items; `calendar.*` manages the generic blocks and the aggregated view.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `calendar.add_item`
- `calendar.list_items`
- `calendar.update_item`
- `calendar.delete_item`
- `calendar.agenda`
- `calendar.sync`
- `calendar.due_reminders`
- `calendar.ack_reminder`
<!-- END GENERATED: action-list -->

## Decision rules

- Generic time block only -> `calendar.add_item`. Real task -> `task.create`, event -> `event.create`, habit -> `habit.create`, meal -> `meal_plan.add`, subscription -> `subscription.create`, fitness session -> `fitness.create_session`.
- Day agenda -> `calendar.agenda` (defaults to today).
- Broad time-range listing -> `calendar.list_items`.
- Reconcile generated items -> `calendar.sync`.
- Due reminders -> `calendar.due_reminders`.
- Dismiss a reminder -> `calendar.ack_reminder`.
- `end_at` must be after `start_at`.
- AdamHUB enforces non-overlap across tasks, meals, events, subscriptions, manual items, and fitness sessions. On an overlap error, propose a new free slot instead of insisting on the same one.

## Enums

- category: `general|task|event|subscription|meal`
- source: `manual|task|habit|event|subscription|meal_plan|fitness_session`

## Safety

- Confirm before `calendar.delete_item`.
- Generated items are read-only here: update or delete them from their source module, not via `calendar.update_item` / `calendar.delete_item`.
- If `item_id` is unknown, resolve it with `calendar.list_items` or `calendar.agenda` first.
- Reminders are minute offsets before the start time (default `[60]`); pass a list in `reminder_offsets_min` to override.

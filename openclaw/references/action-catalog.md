# AdamHUB Action Catalog

Authoritative reference for `POST /api/v1/skill/execute`.

Request shape:

```json
{
  "action": "<action_name>",
  "input": {}
}
```

## Dashboard

- `dashboard.overview`

## Tasks

- `task.create`
- `task.list`
- `task.update`
- `task.complete`

## Finance

- `finance.add_transaction`
- `finance.list_transactions`
- `finance.create_budget`
- `finance.list_budgets`
- `finance.month_summary`

## Groceries

- `grocery.add_item`
- `grocery.list_items`
- `grocery.update_item`
- `grocery.check_item`
- `grocery.delete_item`

## Recipes

- `recipe.add`
- `recipe.list`
- `recipe.get`

## Meal Plans

- `meal_plan.add`
- `meal_plan.list`
- `meal_plan.update`
- `meal_plan.delete`
- `meal_plan.sync_groceries`
- `meal_plan.confirm_cooked`
- `meal_plan.unconfirm_cooked`
- `meal_plan.log_cooked`

## Calendar

- `calendar.add_item`
- `calendar.list_items`
- `calendar.update_item`
- `calendar.delete_item`
- `calendar.agenda`
- `calendar.sync`
- `calendar.due_reminders`
- `calendar.ack_reminder`

## Habits

- `habit.create`
- `habit.list`
- `habit.set_active`
- `habit.log`
- `habit.list_logs`

## Goals

- `goal.create`
- `goal.list`
- `goal.get`
- `goal.update`
- `goal.add_milestone`
- `goal.list_milestones`
- `goal.update_milestone`

## Events

- `event.create`
- `event.list`
- `event.upcoming`
- `event.get`
- `event.update`
- `event.delete`

## Subscriptions

- `subscription.create`
- `subscription.list`
- `subscription.get`
- `subscription.update`
- `subscription.upcoming`
- `subscription.projection`

## Pantry

- `pantry.add_item`
- `pantry.list_items`
- `pantry.update_item`
- `pantry.consume_item`
- `pantry.delete_item`
- `pantry.overview`

## Notes

- `note.create`
- `note.list`
- `note.get`
- `note.update`
- `note.delete`
- `note.journal`

## Linear

- `linear.projects`
- `linear.issues`
- `linear.issue_create`
- `linear.sync`

## Field highlights

- money dates: `occurred_at` in ISO datetime
- budget month: `YYYY-MM`
- date fields: `YYYY-MM-DD`
- enums are strict and case-sensitive
- update actions require id + at least one field to patch

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

## Fitness

- `fitness.overview`
- `fitness.list_sessions`
- `fitness.create_session`
- `fitness.update_session`
- `fitness.complete_session`
- `fitness.delete_session`
- `fitness.list_measurements`
- `fitness.add_measurement`
- `fitness.update_measurement`
- `fitness.delete_measurement`

## Groceries and supermarket

- `supermarket.list_stores`
- `supermarket.search`
- `grocery.add_item`
- `grocery.list_items`
- `grocery.update_item`
- `grocery.check_item`
- `grocery.delete_item`

## Video intake

- `video.fetch`

## Recipes

- `recipe.add`
- `recipe.list`
- `recipe.get`
- `recipe.update`
- `recipe.confirm_cooked`
- `recipe.delete`

## Meal plans

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

## Patrimony

- `patrimony.overview`
- `patrimony.list_accounts`
- `patrimony.add_account`
- `patrimony.update_account`
- `patrimony.delete_account`
- `patrimony.list_goals`
- `patrimony.add_goal`
- `patrimony.update_goal`
- `patrimony.delete_goal`

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

## Field highlights

- money datetimes: ISO 8601
- budget month: `YYYY-MM`
- date fields: `YYYY-MM-DD`
- enums are strict and case-sensitive
- update actions require an id plus at least one field to patch
- `supermarket.search` must be the source for store-backed grocery and pantry metadata
- `recipe.add` and `recipe.update` accept `steps`, `utensils`, source metadata, and store-backed ingredient fields
- `recipe.confirm_cooked` consumes pantry directly from a recipe
- `meal_plan.confirm_cooked` consumes pantry from a planned recipe
- `meal_plan.unconfirm_cooked` restores pantry stock
- `fitness.create_session` and `fitness.update_session` are subject to calendar overlap validation
- `patrimony.overview` returns net worth, active accounts, and savings goals
- `video.fetch` returns normalized metadata, transcript, and transcript segments; when captions are unavailable it can fall back to local Whisper

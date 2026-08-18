# AdamHUB Action Catalog

Authoritative reference for `POST /api/v1/skill/execute`.

Request shape:

```json
{
  "action": "<action_name>",
  "input": {}
}
```

<!-- BEGIN GENERATED: action-catalog (source: app/skill/actions.py ACTION_CATALOG) -->
## Dashboard

- `dashboard.overview` — Return current productivity and life overview
  - `input_schema`: (none)

## Tasks

- `task.create` — Create a one-shot task. For a scheduled task, use due_at plus estimated_minutes. If the user wants a checklist or steps, store them in subtasks. Do not use calendar.add_item for normal tasks.
  - `input_schema`: `title`: string, `description`: string?, `subtasks`: [{id?, title, completed}]?, `schedule_mode`: none|once|daily|weekly?, `schedule_time`: HH:MM?, `schedule_weekday`: 0=Monday..6=Sunday?, `due_at`: datetime?, `priority`: low|medium|high|urgent, `estimated_minutes`: int?, `tags`: string[]?

- `task.list` — List tasks with optional status filter
  - `input_schema`: `status`: todo|in_progress|done|blocked?, `only_open`: bool?, `limit`: int?

- `task.update` — Update an existing task. Use this to change title, description, checklist, timing, duration, or status. Keep task scheduling inside task.update, not calendar.update_item.
  - `input_schema`: `task_id`: int, `title`: string?, `description`: string?, `subtasks`: [{id?, title, completed}]?, `schedule_mode`: none|once|daily|weekly?, `schedule_time`: HH:MM?, `schedule_weekday`: 0=Monday..6=Sunday?, `due_at`: datetime?, `priority`: low|medium|high|urgent?, `status`: todo|in_progress|done|blocked?, `estimated_minutes`: int?, `tags`: string[]?

- `task.complete` — Mark a task as done
  - `input_schema`: `task_id`: int

- `task.delete` — Delete a task
  - `input_schema`: `task_id`: int

## Finance

- `finance.add_transaction` — Add an income or expense transaction
  - `input_schema`: `kind`: income|expense, `amount`: float, `currency`: string?, `category`: string, `note`: string?, `occurred_at`: datetime?, `is_recurring`: bool?

- `finance.list_transactions` — List transactions
  - `input_schema`: `kind`: income|expense?, `year`: int?, `month`: int?, `limit`: int?

- `finance.create_budget` — Create a monthly category budget
  - `input_schema`: `month`: YYYY-MM, `category`: string, `monthly_limit`: float, `currency`: string?, `alert_threshold`: float?

- `finance.list_budgets` — List budgets with optional month
  - `input_schema`: `month`: YYYY-MM?

- `finance.month_summary` — Compute month financial summary
  - `input_schema`: `year`: int?, `month`: int?

## Fitness

- `fitness.overview` — Return the fitness dashboard overview
  - `input_schema`: (none)

- `fitness.list_sessions` — List fitness sessions
  - `input_schema`: `limit`: int?

- `fitness.create_session` — Create a fitness session
  - `input_schema`: `title`: string, `session_type`: strength|cardio|mobility|recovery|mixed?, `planned_at`: datetime?, `duration_minutes`: int?, `exercises`: [{name, mode, reps, duration_minutes, note}|string]?, `note`: string?

- `fitness.update_session` — Update a fitness session
  - `input_schema`: `session_id`: int, `title`: string?, `session_type`: strength|cardio|mobility|recovery|mixed?, `planned_at`: datetime?, `duration_minutes`: int?, `exercises`: [{name, mode, reps, duration_minutes, note}|string]?, `note`: string?, `status`: planned|completed|skipped?, `actual_duration_minutes`: int?, `effort_rating`: int?, `calories_burned`: float?

- `fitness.complete_session` — Mark a fitness session as completed
  - `input_schema`: `session_id`: int, `note`: string?, `actual_duration_minutes`: int?, `effort_rating`: int?, `calories_burned`: float?

- `fitness.delete_session` — Delete a fitness session
  - `input_schema`: `session_id`: int

- `fitness.list_measurements` — List fitness measurements
  - `input_schema`: `limit`: int?

- `fitness.add_measurement` — Add a fitness measurement
  - `input_schema`: `recorded_at`: datetime?, `body_weight_kg`: float?, `body_fat_pct`: float?, `resting_hr`: int?, `sleep_hours`: float?, `steps`: int?, `note`: string?

- `fitness.update_measurement` — Update a fitness measurement
  - `input_schema`: `measurement_id`: int, `recorded_at`: datetime?, `body_weight_kg`: float?, `body_fat_pct`: float?, `resting_hr`: int?, `sleep_hours`: float?, `steps`: int?, `note`: string?

- `fitness.delete_measurement` — Delete a fitness measurement
  - `input_schema`: `measurement_id`: int

## Groceries and supermarket

- `supermarket.list_stores` — List supported supermarket stores and capabilities
  - `input_schema`: (none)

- `supermarket.list_connections` — List saved supermarket connections (cookie sets) across all stores. Each entry has an id, label, store, is_active flag and cookies_count. Multiple connections per store are allowed (e.g. user + spouse).
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan?

- `supermarket.import_connection` — Save a fresh cookie set (or best-effort credentials) for a supermarket. Used by the AdamHUB Connect Chrome extension after a successful login. `cookies` is the array dumped via chrome.cookies.getAll. Set activate=true to make this connection the default consumer for the store. `credentials` ({username, password}) is a best-effort fallback when the store has no captcha/2FA on programmatic login; cookies remain the reliable path.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan, `label`: string, `cookies`: object[]?, `credentials`: object?, `activate`: bool?, `connection_id`: int?

- `supermarket.activate_connection` — Switch the active connection for a store (search/cart/orders will use this account next).
  - `input_schema`: `connection_id`: int

- `supermarket.delete_connection` — Delete a saved supermarket connection.
  - `input_schema`: `connection_id`: int

- `supermarket.list_offering_contexts` — List the Auchan stores selectable for an address. Each entry carries `seller_id`, `store_reference`, `channel`, `name`, `address` and `distance` — feed them to `supermarket.select_auchan_store`.
  - `input_schema`: `zipcode`: string, `city`: string, `latitude`: float, `longitude`: float, `country`: string?

- `supermarket.select_auchan_store` — Select the Auchan store used for search (POST /journey/update + persist). Auchan prices are only server-rendered once a store is selected; searching without one returns a 400 'sélectionnez un magasin'.
  - `input_schema`: `seller_id`: string, `store_reference`: string, `store_label`: string, `channel`: string?, `location_label`: string?, `zipcode`: string?, `city`: string?, `country`: string?, `latitude`: float?, `longitude`: float?

- `supermarket.search` — Search a supermarket and cache the normalized results. `store` accepts 'intermarche' (JSON API), 'carrefour' (JSON endpoint), 'leclerc' (JSON API + cookies) or 'auchan' (server-rendered HTML; works without login but requires a selected store via `supermarket.select_auchan_store`).
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan?, `queries`: string[], `max_results`: int?, `promotions_only`: bool?

- `grocery.add_item` — Add an item to grocery list
  - `input_schema`: `name`: string, `quantity`: float?, `unit`: string?, `category`: string?, `image_url`: string?, `store_label`: string?, `external_id`: string?, `packaging`: string?, `price_text`: string?, `product_url`: string?, `priority`: int?, `note`: string?

- `grocery.list_items` — List grocery items
  - `input_schema`: `checked`: bool?, `limit`: int?

- `grocery.update_item` — Update a grocery item
  - `input_schema`: `item_id`: int, `quantity`: float?, `unit`: string?, `category`: string?, `checked`: bool?, `priority`: int?, `note`: string?

- `grocery.check_item` — Mark grocery item checked or unchecked
  - `input_schema`: `item_id`: int, `checked`: bool?

- `grocery.delete_item` — Delete a grocery item
  - `input_schema`: `item_id`: int

## Video intake

- `video.fetch` — Fetch transcript and description from a YouTube, Instagram, or TikTok URL
  - `input_schema`: `url`: string

## Recipes

- `recipe.add` — Create a recipe with optional ingredients
  - `input_schema`: `name`: string, `description`: string?, `instructions`: string, `steps`: string[]?, `utensils`: string[]?, `prep_minutes`: int?, `cook_minutes`: int?, `servings`: int?, `tags`: string[]?, `source_url`: string?, `source_platform`: string?, `source_title`: string?, `source_description`: string?, `source_transcript`: string?, `ingredients`: [{name, quantity, unit, note, category, cache_id}]?

- `recipe.list` — List recipes
  - `input_schema`: `limit`: int?

- `recipe.get` — Get one recipe by id
  - `input_schema`: `recipe_id`: int

- `recipe.update` — Update a recipe
  - `input_schema`: `recipe_id`: int, `name`: string?, `description`: string?, `instructions`: string?, `steps`: string[]?, `utensils`: string[]?, `prep_minutes`: int?, `cook_minutes`: int?, `servings`: int?, `tags`: string[]?, `source_url`: string?, `source_platform`: string?, `source_title`: string?, `source_description`: string?, `source_transcript`: string?, `ingredients`: [{name, quantity, unit, note, category, cache_id}]?

- `recipe.confirm_cooked` — Confirm a recipe was cooked and consume pantry ingredients (idempotent; undo with recipe.unconfirm_cooked)
  - `input_schema`: `recipe_id`: int, `servings_override`: int?, `note`: string?

- `recipe.unconfirm_cooked` — Undo a recipe-level cooked confirmation and restore pantry stock
  - `input_schema`: `recipe_id`: int

- `recipe.delete` — Delete a recipe and its dependent recipe ingredients / meal plans
  - `input_schema`: `recipe_id`: int

## Meal plans

- `meal_plan.add` — Plan a recipe at a specific datetime
  - `input_schema`: `planned_at`: datetime?, `planned_for`: YYYY-MM-DD? (legacy), `slot`: breakfast|lunch|dinner? (legacy), `recipe_id`: int, `servings_override`: int?, `note`: string?, `auto_add_missing_ingredients`: bool?

- `meal_plan.log_cooked` — Log a recipe as cooked without pre-planning
  - `input_schema`: `recipe_id`: int, `cooked_at`: datetime?, `servings_override`: int?, `note`: string?

- `meal_plan.list` — List meal plans
  - `input_schema`: `date_from`: YYYY-MM-DD?, `date_to`: YYYY-MM-DD?, `slot`: breakfast|lunch|dinner? (legacy), `limit`: int?

- `meal_plan.update` — Update one meal plan
  - `input_schema`: `meal_plan_id`: int, `planned_at`: datetime?, `planned_for`: YYYY-MM-DD? (legacy), `slot`: breakfast|lunch|dinner? (legacy), `recipe_id`: int?, `servings_override`: int?, `note`: string?, `auto_add_missing_ingredients`: bool?

- `meal_plan.delete` — Delete one meal plan
  - `input_schema`: `meal_plan_id`: int

- `meal_plan.sync_groceries` — Sync missing ingredients to grocery list for one meal plan
  - `input_schema`: `meal_plan_id`: int

- `meal_plan.confirm_cooked` — Confirm meal was cooked and consume pantry ingredients
  - `input_schema`: `meal_plan_id`: int, `note`: string?

- `meal_plan.unconfirm_cooked` — Undo cooked confirmation and restore pantry
  - `input_schema`: `meal_plan_id`: int

## Calendar

- `calendar.add_item` — Create a manual calendar block only when the user wants a generic time slot and not a real task, habit, event, meal, subscription, or fitness session.
  - `input_schema`: `title`: string, `description`: string?, `start_at`: datetime, `end_at`: datetime, `all_day`: bool?, `category`: general|task|event|subscription|meal?, `notification_enabled`: bool?, `reminder_offsets_min`: int[]?, `metadata`: object?

- `calendar.list_items` — List calendar items
  - `input_schema`: `from_at`: datetime?, `to_at`: datetime?, `category`: general|task|event|subscription|meal?, `source`: manual|task|habit|event|subscription|meal_plan|fitness_session?, `include_completed`: bool?, `generated_only`: bool?, `limit`: int?

- `calendar.update_item` — Update calendar item
  - `input_schema`: `item_id`: int, `title`: string?, `description`: string?, `start_at`: datetime?, `end_at`: datetime?, `all_day`: bool?, `category`: general|task|event|subscription|meal?, `completed`: bool?, `notification_enabled`: bool?, `reminder_offsets_min`: int[]?, `metadata`: object?

- `calendar.delete_item` — Delete calendar item
  - `input_schema`: `item_id`: int

- `calendar.agenda` — List day agenda
  - `input_schema`: `day`: YYYY-MM-DD?, `include_completed`: bool?

- `calendar.sync` — Sync tasks/events/subscriptions/meal plans into calendar
  - `input_schema`: (none)

- `calendar.due_reminders` — List due reminders in next N minutes
  - `input_schema`: `within_minutes`: int?

- `calendar.ack_reminder` — Acknowledge reminders for a calendar item
  - `input_schema`: `item_id`: int

## Habits

- `habit.create` — Create a habit
  - `input_schema`: `name`: string, `description`: string?, `frequency`: daily|weekly?, `target_per_period`: int?, `schedule_time`: HH:MM?, `schedule_times`: HH:MM[]?, `schedule_weekday`: 0=Monday..6=Sunday?, `schedule_weekdays`: 0..6[]?, `duration_minutes`: int?

- `habit.list` — List habits
  - `input_schema`: `active_only`: bool?

- `habit.update` — Update a habit
  - `input_schema`: `habit_id`: int, `name`: string?, `description`: string?, `frequency`: daily|weekly?, `target_per_period`: int?, `schedule_time`: HH:MM?, `schedule_times`: HH:MM[]?, `schedule_weekday`: 0=Monday..6=Sunday?, `schedule_weekdays`: 0..6[]?, `duration_minutes`: int?, `active`: bool?

- `habit.set_active` — Activate or deactivate a habit
  - `input_schema`: `habit_id`: int, `active`: bool

- `habit.log` — Log completion for a habit
  - `input_schema`: `habit_id`: int, `value`: int?, `note`: string?

- `habit.list_logs` — List logs for one habit
  - `input_schema`: `habit_id`: int, `limit`: int?

## Goals

- `goal.create` — Create a goal
  - `input_schema`: `title`: string, `description`: string?, `status`: planned|active|completed|paused|cancelled?, `progress_percent`: int?, `target_date`: YYYY-MM-DD?, `tags`: string[]?

- `goal.list` — List goals
  - `input_schema`: `status`: planned|active|completed|paused|cancelled?, `limit`: int?

- `goal.get` — Get one goal
  - `input_schema`: `goal_id`: int

- `goal.update` — Update a goal
  - `input_schema`: `goal_id`: int, `title`: string?, `description`: string?, `status`: planned|active|completed|paused|cancelled?, `progress_percent`: int?, `target_date`: YYYY-MM-DD?, `tags`: string[]?

- `goal.add_milestone` — Add a milestone to a goal
  - `input_schema`: `goal_id`: int, `title`: string, `due_at`: datetime?

- `goal.list_milestones` — List milestones for a goal
  - `input_schema`: `goal_id`: int, `limit`: int?

- `goal.update_milestone` — Update a goal milestone
  - `input_schema`: `goal_id`: int, `milestone_id`: int, `title`: string?, `due_at`: datetime?, `completed`: bool?

## Events

- `event.create` — Create calendar event
  - `input_schema`: `title`: string, `description`: string?, `start_at`: datetime, `end_at`: datetime, `location`: string?, `type`: personal|work|health|finance|social?, `all_day`: bool?, `tags`: string[]?

- `event.list` — List events
  - `input_schema`: `from_at`: datetime?, `to_at`: datetime?, `type`: personal|work|health|finance|social?, `limit`: int?

- `event.upcoming` — List upcoming events
  - `input_schema`: `days`: int?, `type`: personal|work|health|finance|social?

- `event.get` — Get one event
  - `input_schema`: `event_id`: int

- `event.update` — Update an event
  - `input_schema`: `event_id`: int, `title`: string?, `description`: string?, `start_at`: datetime?, `end_at`: datetime?, `location`: string?, `type`: personal|work|health|finance|social?, `all_day`: bool?, `tags`: string[]?

- `event.delete` — Delete an event
  - `input_schema`: `event_id`: int

## Subscriptions

- `subscription.create` — Create subscription
  - `input_schema`: `name`: string, `category`: string?, `amount`: float, `currency`: string?, `interval`: weekly|monthly|yearly?, `next_due_date`: YYYY-MM-DD, `autopay`: bool?, `active`: bool?, `note`: string?

- `subscription.list` — List subscriptions
  - `input_schema`: `active_only`: bool?, `limit`: int?

- `subscription.get` — Get one subscription
  - `input_schema`: `subscription_id`: int

- `subscription.update` — Update subscription
  - `input_schema`: `subscription_id`: int, `name`: string?, `category`: string?, `amount`: float?, `currency`: string?, `interval`: weekly|monthly|yearly?, `next_due_date`: YYYY-MM-DD?, `autopay`: bool?, `active`: bool?, `note`: string?

- `subscription.upcoming` — List upcoming subscriptions
  - `input_schema`: `days`: int?

- `subscription.projection` — Compute monthly and yearly subscription projection
  - `input_schema`: `currency`: string?

## Patrimony

- `patrimony.overview` — Return patrimony overview with net worth, accounts, and savings goals
  - `input_schema`: (none)

- `patrimony.list_accounts` — List patrimony accounts
  - `input_schema`: `active_only`: bool?

- `patrimony.add_account` — Create a patrimony account
  - `input_schema`: `name`: string, `account_type`: checking|savings|investment|crypto|other?, `balance`: float?, `currency`: string?, `institution`: string?, `note`: string?

- `patrimony.update_account` — Update a patrimony account
  - `input_schema`: `account_id`: int, `name`: string?, `account_type`: checking|savings|investment|crypto|other?, `balance`: float?, `currency`: string?, `institution`: string?, `note`: string?, `is_active`: bool?

- `patrimony.delete_account` — Delete a patrimony account
  - `input_schema`: `account_id`: int

- `patrimony.list_goals` — List savings goals
  - `input_schema`: (none)

- `patrimony.add_goal` — Create a savings goal
  - `input_schema`: `title`: string, `target_amount`: float, `current_amount`: float?, `currency`: string?, `target_date`: YYYY-MM-DD?, `account_id`: int?, `note`: string?

- `patrimony.update_goal` — Update a savings goal
  - `input_schema`: `goal_id`: int, `title`: string?, `target_amount`: float?, `current_amount`: float?, `currency`: string?, `target_date`: YYYY-MM-DD?, `account_id`: int?, `note`: string?, `completed`: bool?

- `patrimony.delete_goal` — Delete a savings goal
  - `input_schema`: `goal_id`: int

## Pantry

- `pantry.add_item` — Add pantry item
  - `input_schema`: `name`: string, `quantity`: float?, `unit`: string?, `category`: string?, `min_quantity`: float?, `expires_at`: YYYY-MM-DD?, `location`: string?, `note`: string?

- `pantry.list_items` — List pantry items
  - `input_schema`: `low_stock_only`: bool?, `expiring_in_days`: int?, `limit`: int?

- `pantry.update_item` — Update pantry item
  - `input_schema`: `item_id`: int, `quantity`: float?, `unit`: string?, `category`: string?, `min_quantity`: float?, `expires_at`: YYYY-MM-DD?, `location`: string?, `note`: string?

- `pantry.consume_item` — Decrease pantry item quantity
  - `input_schema`: `item_id`: int, `amount`: float

- `pantry.delete_item` — Delete pantry item
  - `input_schema`: `item_id`: int

- `pantry.overview` — Get pantry overview
  - `input_schema`: `days`: int?

## Notes

- `note.create` — Create note
  - `input_schema`: `title`: string, `content`: string, `kind`: note|journal|idea?, `tags`: string[]?, `pinned`: bool?, `mood`: 1..10?

- `note.list` — List notes
  - `input_schema`: `kind`: note|journal|idea?, `tag`: string?, `q`: string?, `pinned`: bool?, `limit`: int?

- `note.get` — Get one note
  - `input_schema`: `note_id`: int

- `note.update` — Update note
  - `input_schema`: `note_id`: int, `title`: string?, `content`: string?, `kind`: note|journal|idea?, `tags`: string[]?, `pinned`: bool?, `mood`: 1..10?

- `note.delete` — Delete note
  - `input_schema`: `note_id`: int

- `note.journal` — List journal entries
  - `input_schema`: `from_date`: YYYY-MM-DD?, `to_date`: YYYY-MM-DD?, `limit`: int?

<!-- END GENERATED: action-catalog -->

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

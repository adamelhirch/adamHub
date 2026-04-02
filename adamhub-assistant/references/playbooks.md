# AdamHUB Playbooks

Use these sequences for high-confidence multi-step execution.

## Daily focus reset

Goal: reduce overload and produce a clear action list.

1. `dashboard.overview`
2. `task.list` with `only_open=true`
3. `calendar.agenda` if timing matters
4. propose the top actions
5. execute approved `task.update` or `task.complete`

## Weekly groceries refresh

Goal: keep the list actionable before shopping.

1. `grocery.list_items` with `checked=false`
2. inspect pantry gaps if relevant with `pantry.overview` or `pantry.list_items`
3. for store-backed requests, call `supermarket.search`
4. add selected results via `grocery.add_item`
5. if no valid result exists, create a generic grocery item
6. mark bought items through `grocery.check_item`

## Meal planning sprint

Goal: choose meals and build a trustworthy shopping list.

1. `recipe.list`
2. `recipe.get` for the selected recipes
3. `meal_plan.add`
4. inspect missing ingredients
5. `supermarket.search` for each missing ingredient or tight batch
6. create groceries only from selected results or generic fallbacks
7. `grocery.list_items` to verify
8. when cooked, `meal_plan.confirm_cooked`
9. if confirmation was wrong, `meal_plan.unconfirm_cooked`

## Video to recipe

Goal: turn an Instagram, TikTok, or YouTube video into a recipe entry.

1. `video.fetch`
2. infer recipe name, ingredients, utensils, and steps from transcript + description
3. search supermarket only if store-backed ingredients are desired
4. `recipe.add` or `recipe.update`
5. if planning is needed, `meal_plan.add`
6. if the user wants immediate pantry deduction without planning, `recipe.confirm_cooked`

## Fitness week setup

Goal: plan sessions without colliding with existing scheduled work.

1. `fitness.overview`
2. `fitness.list_sessions`
3. `calendar.list_items` or `calendar.agenda`
4. identify free slots
5. `fitness.create_session`
6. after the session is done, `fitness.complete_session`

## Patrimony review

Goal: understand net worth and update savings goals.

1. `patrimony.overview`
2. `patrimony.list_accounts`
3. `patrimony.list_goals`
4. optional `patrimony.update_account`
5. optional `patrimony.update_goal`

## Daily unified agenda

Goal: keep web, calendar subscriptions, and AI aligned on one timeline.

1. `calendar.sync`
2. `calendar.agenda`
3. `calendar.due_reminders`
4. `calendar.ack_reminder`

## Monthly money review

Goal: identify spend pattern and net position.

1. `finance.month_summary`
2. `finance.list_transactions`
3. `finance.list_budgets`
4. optional `finance.create_budget`
5. optional `subscription.projection`

## Cross-domain sunday planning

Goal: align tasks, money, groceries, meals, fitness, and patrimony.

1. `dashboard.overview`
2. `finance.month_summary`
3. `task.list`
4. `recipe.list`
5. `grocery.list_items`
6. `fitness.overview`
7. `patrimony.overview`
8. propose a concise weekly plan
9. execute only approved writes


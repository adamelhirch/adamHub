# AdamHUB Playbooks

Use these sequences for high-confidence multi-step execution.

## Daily focus reset

Goal: reduce overload and produce a clear action list.

1. `dashboard.overview`
2. `task.list` with `only_open=true` and `limit=50`
3. If too many open tasks, propose top 3 by urgency due date.
4. On user choice, run `task.update` for priority/status/due date.
5. Close done work with `task.complete`.

## Monthly money review

Goal: identify spend pattern and net position.

1. `finance.month_summary` for chosen month.
2. If user asks detail, call `finance.list_transactions` with `year` and `month`.
3. If over budget concern, call `finance.list_budgets` for same month.
4. If missing budget, propose and create with `finance.create_budget`.

## Weekly groceries refresh

Goal: keep list actionable before shopping.

1. `grocery.list_items` with `checked=false`.
2. Add missing items via `grocery.add_item`.
3. Adjust quantities via `grocery.update_item`.
4. During checkout, mark bought via `grocery.check_item`.

## Meal planning sprint

Goal: choose meals and build shopping list.

1. `recipe.list`
2. For selected recipes, `recipe.get` to inspect ingredients.
3. Create slots with `meal_plan.add` (`auto_add_missing_ingredients=true`).
4. If needed, force refresh with `meal_plan.sync_groceries`.
5. Confirm resulting list via `grocery.list_items` with `checked=false`.
6. After meal is actually done, call `meal_plan.confirm_cooked` to consume pantry.
7. If confirmation was wrong, call `meal_plan.unconfirm_cooked` to restore pantry.

## Daily unified agenda

Goal: keep iOS/web/AI perfectly aligned on one timeline.

1. `calendar.sync`
2. `calendar.agenda` for current day
3. `calendar.due_reminders` with `within_minutes=180`
4. Acknowledge delivered reminders with `calendar.ack_reminder`

## Habit reboot

Goal: restart routine with measurable tracking.

1. `habit.list` with `active_only=true`
2. If needed, create habit via `habit.create`.
3. Log completion using `habit.log`.
4. Echo streak value after each log.
5. Pause noisy habits only with explicit confirmation via `habit.set_active`.

## Cross-domain sunday planning

Goal: align tasks, money, meals, and habits.

1. `dashboard.overview`
2. `finance.month_summary`
3. `task.list` with `only_open=true`
4. `recipe.list`
5. `grocery.list_items` with `checked=false`
6. `habit.list` with `active_only=true`
7. Propose a concise weekly plan and execute approved writes.

## Long-term roadmap review

Goal: align goals, milestones, and calendar.

1. `goal.list` with status `active`
2. For each selected goal, `goal.list_milestones`
3. `event.upcoming` with `days=14`
4. Optional updates with `goal.update` and `goal.update_milestone`

## Monthly fixed-cost audit

Goal: understand recurring cost pressure and due dates.

1. `subscription.list` with `active_only=true`
2. `subscription.projection`
3. `subscription.upcoming` with `days=30`
4. Optional cleanup with `subscription.update` to deactivate stale services

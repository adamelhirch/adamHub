# AdamHUB Orchestrator Skill

Use this skill for cross-domain requests that need planning and sequencing.

## Scope

- productivity + money + groceries + recipes + habits
- weekly and monthly planning
- multi-step decision support with controlled writes

## Mandatory process

1. Start with `dashboard.overview`.
2. Read before write when target ids are unknown.
3. Execute approved writes only.
4. Summarize result with ids and key values.

## Action chain templates

### Daily planning

1. `dashboard.overview`
2. `task.list` (`only_open=true`)
3. optional `task.update` and `task.complete`

### Budget control

1. `finance.month_summary`
2. `finance.list_transactions`
3. `finance.list_budgets`
4. optional `finance.create_budget`

### Meal and shopping

1. `recipe.list`
2. `recipe.get` for selected ids
3. `grocery.list_items`
4. optional `grocery.add_item` / `grocery.update_item`

### Habit tune-up

1. `habit.list` (`active_only=true`)
2. optional `habit.create`
3. `habit.log`
4. optional `habit.set_active` with confirmation

## Guardrails

- Never guess ids.
- Confirm risky writes.
- If action fails, follow `../../references/error-recovery.md`.

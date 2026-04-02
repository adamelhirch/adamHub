# AdamHUB Orchestrator Skill

Use this skill for cross-domain requests that need sequencing across multiple AdamHUB modules.

## Scope

- tasks
- money
- groceries and pantry
- recipes and meal plans
- calendar
- fitness
- patrimony

## Mandatory process

1. Start with `dashboard.overview`.
2. Read before write when ids are unknown.
3. Respect calendar conflicts and supermarket rules.
4. Execute only approved writes.
5. Summarize the result with ids and next steps.

## Action chain templates

### Daily planning

1. `dashboard.overview`
2. `task.list`
3. `calendar.agenda`
4. optional `task.update` and `task.complete`

### Weekly food planning

1. `recipe.list`
2. `recipe.get`
3. `meal_plan.add`
4. `supermarket.search`
5. `grocery.add_item`

### Fitness + calendar

1. `fitness.overview`
2. `fitness.list_sessions`
3. `calendar.list_items`
4. optional `fitness.create_session`

### Money + patrimony

1. `finance.month_summary`
2. `subscription.projection`
3. `patrimony.overview`
4. optional `patrimony.update_account` or `patrimony.update_goal`

## Guardrails

- Never guess ids.
- Never fabricate store metadata.
- Never bypass overlap errors.
- Confirm destructive writes.
- If an action fails, follow `../../references/error-recovery.md`.


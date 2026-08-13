# AdamHUB Fitness Skill

Use for workout planning, session execution tracking, and body measurements.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
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
<!-- END GENERATED: action-list -->

## Rules

- Sessions must respect calendar overlap rules.
- Exercises can be tracked by `reps` or `duration`.
- Mark a session complete only once it is actually done.
- Use measurements for body metrics, not sessions.


# AdamHUB Fitness Skill

Use for workout planning, session execution tracking, and body measurements.

## Actions

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

## Rules

- Sessions must respect calendar overlap rules.
- Exercises can be tracked by `reps` or `duration`.
- Mark a session complete only once it is actually done.
- Use measurements for body metrics, not sessions.


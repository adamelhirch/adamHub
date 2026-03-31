# AdamHUB Tasks Skill

Use for one-shot tasks.

If the user is describing something recurring like a routine, a ritual, or a habit, do not create a normal task. Switch to the habits skill and use `habit.*`.

## Actions

- `task.create`
- `task.list`
- `task.update`
- `task.complete`

## Minimal decision rules

- Need task id and missing -> call `task.list` first.
- User says "done" -> `task.complete`.
- User edits priority/date/title -> `task.update`.
- Recurring intent -> `habit.create`, not `task.create`.
- Scheduled one-shot task -> `task.create` or `task.update` with `due_at` and `estimated_minutes`.
- Do not use `calendar.add_item` for a normal task request.
- If the user wants steps, checklist, or "5 etapes" and there is no dedicated structured task field, put the numbered list in `description`.
- Ask for missing step content once at most. If the user repeats the same request unchanged, use a neutral numbered placeholder list and say so.

## Valid enums

- priority: `low|medium|high|urgent`
- status: `todo|in_progress|done|blocked`

## Payload snippets

Create:

```json
{"action":"task.create","input":{"title":"Call bank","priority":"high"}}
```

Create scheduled task:

```json
{"action":"task.create","input":{"title":"Call bank","due_at":"2026-03-31T17:00:00Z","estimated_minutes":30,"priority":"high"}}
```

Create scheduled task with checklist in description:

```json
{"action":"task.create","input":{"title":"Task (5 steps)","description":"1. Step 1\n2. Step 2\n3. Step 3\n4. Step 4\n5. Step 5","due_at":"2026-03-31T17:00:00Z","estimated_minutes":30,"priority":"medium"}}
```

List open:

```json
{"action":"task.list","input":{"only_open":true,"limit":50}}
```

Update:

```json
{"action":"task.update","input":{"task_id":8,"status":"in_progress","due_at":"2026-03-03T18:00:00Z"}}
```

Complete:

```json
{"action":"task.complete","input":{"task_id":8}}
```

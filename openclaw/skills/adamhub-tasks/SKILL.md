# AdamHUB Tasks Skill

Use for all task lifecycle operations.

## Actions

- `task.create`
- `task.list`
- `task.update`
- `task.complete`

## Minimal decision rules

- Need task id and missing -> call `task.list` first.
- User says "done" -> `task.complete`.
- User edits priority/date/title -> `task.update`.

## Valid enums

- priority: `low|medium|high|urgent`
- status: `todo|in_progress|done|blocked`

## Payload snippets

Create:

```json
{"action":"task.create","input":{"title":"Call bank","priority":"high"}}
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

# Assistant Chat SSE Protocol Contract

**Endpoint**: `POST /api/v1/assistant/chat`  
**Authentication**: Bearer JWT (SaaS user) or `X-API-Key` (Owner fallback)  
**Content-Type**: `application/json`  
**Accept**: `text/event-stream`

---

## 1. Request Body

```json
{
  "message": "Planifie ma recette de Risotto pour demain soir à 20h",
  "history": [
    {
      "role": "user",
      "content": "Quelles sont mes recettes disponibles ?"
    },
    {
      "role": "assistant",
      "content": "Vous avez enregistré votre Risotto aux champignons (4 portions)."
    }
  ]
}
```

---

## 2. Server-Sent Events (SSE) Stream

The endpoint streams JSON events with specific `event` headers:

### `event: delta`
Incremental text tokens produced by the assistant.
```text
event: delta
data: {"content": "Je vérifie vos créneaux pour demain soir."}
```

### `event: tool_call`
Notifies the client of an autonomous tool invocation by the assistant.
```text
event: tool_call
data: {"id": "call_abc123", "type": "function", "function": {"name": "calendar__add_item", "arguments": "{\"title\": \"Dîner Risotto\", \"start_at\": \"2026-09-13T20:00:00Z\", \"end_at\": \"2026-09-13T21:00:00Z\", \"force\": false}"}}
```

### `event: tool_result`
The execution result of the tool invocation, scoped to the acting user.
```text
event: tool_result
data: {"action": "calendar.add_item", "success": true, "data": {"conflict": true, "colliding_items": [{"title": "Cinéma", "start_at": "2026-09-13T19:30:00Z", "end_at": "2026-09-13T21:30:00Z"}], "suggested_slots": [{"start_at": "2026-09-13T21:30:00Z", "end_at": "2026-09-13T22:30:00Z"}]}}
```

### `event: done`
Signals the conclusion of the conversational turn and all agent steps.
```text
event: done
data: {"finished": true}
```

def test_skill_manifest_and_execute_action(client, auth_headers):
    manifest = client.get("/api/v1/skill/manifest", headers=auth_headers)
    assert manifest.status_code == 200
    body = manifest.json()
    assert body["name"] == "adamhub-life-skill"
    actions = [item["action"] for item in body["actions"]]
    assert "meal_plan.confirm_cooked" in actions
    assert "meal_plan.unconfirm_cooked" in actions

    executed = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "task.create", "input": {"title": "skill created task", "priority": "medium"}},
    )
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["ok"] is True
    assert payload["action"] == "task.create"
    assert payload["data"]["task"]["title"] == "skill created task"

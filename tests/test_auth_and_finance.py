def test_auth_check_ok(client, auth_headers):
    response = client.get("/api/v1/auth/check", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_auth_check_missing_key_returns_401(client):
    response = client.get("/api/v1/auth/check")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_finance_summary_and_analytics_alias(client, auth_headers):
    tx_payloads = [
        {
            "kind": "income",
            "amount": 2000,
            "currency": "EUR",
            "category": "salary",
            "occurred_at": "2026-03-05T10:00:00Z",
        },
        {
            "kind": "expense",
            "amount": 120,
            "currency": "EUR",
            "category": "groceries",
            "occurred_at": "2026-03-06T10:00:00Z",
        },
    ]
    for payload in tx_payloads:
        created = client.post("/api/v1/finances/transactions", headers=auth_headers, json=payload)
        assert created.status_code == 200

    budget = client.post(
        "/api/v1/finances/budgets",
        headers=auth_headers,
        json={
            "month": "2026-03",
            "category": "groceries",
            "monthly_limit": 300,
            "currency": "EUR",
            "alert_threshold": 0.8,
        },
    )
    assert budget.status_code == 200

    summary = client.get("/api/v1/finances/summary?year=2026&month=3", headers=auth_headers)
    analytics = client.get("/api/v1/finances/analytics?year=2026&month=3", headers=auth_headers)

    assert summary.status_code == 200
    assert analytics.status_code == 200
    assert summary.json() == analytics.json()

    data = summary.json()
    assert data["income"] == 2000.0
    assert data["expense"] == 120.0
    assert data["net"] == 1880.0
    assert data["budgets"][0]["category"] == "groceries"

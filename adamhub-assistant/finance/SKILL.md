# AdamHUB Finance Skill

Use for transaction logging, budget setup, and month summaries.

## Actions

- `finance.add_transaction`
- `finance.list_transactions`
- `finance.create_budget`
- `finance.list_budgets`
- `finance.month_summary`

## Decision rules

- If intent is "spent" or "earned" -> `finance.add_transaction`.
- If user asks trend/details -> `finance.list_transactions`.
- If user asks monthly state -> `finance.month_summary`.
- If budget is missing -> propose `finance.create_budget`.

## Validation

- `kind` required for add: `income|expense`
- `amount` must be positive float
- `month` for budget must be `YYYY-MM`

## Safety

- Confirm transaction when amount > 200.
- Never infer recurring behavior without explicit consent.
- Always echo amount, currency, category, date in response.

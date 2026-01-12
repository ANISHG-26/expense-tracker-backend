# Backend (Expense Tracker POC)

This service implements the Expense Tracker API defined in the context repo:
`../Context Repository/contracts/expense-tracker/openapi.yaml`.

## Setup

1) Create a virtual environment
2) Install dependencies
3) Run the server

Example:

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python app.py

The API runs on http://localhost:3000 by default.

## Lint, tests, and hooks

- Lint: `ruff check .`
- Format: `ruff format .`
- Tests: `pytest`
- Pre-commit: `pre-commit install`

## SQLite

- Default database path: `Backend/expenses.db`
- Override with `DATABASE_PATH=/path/to/db`

## CORS

- Enabled for all origins in the POC.

## Docker (shared)

Use the shared compose file in the context repo:
`../Context Repository/shared/docker-compose.yml`

Run:
`docker compose -f "../Context Repository/shared/docker-compose.yml" up --build`

Or:
`powershell -File run-shared.ps1 -Action compose`

## Contract guard (shared)

Run:
`powershell -ExecutionPolicy Bypass -File "../Context Repository/shared/scripts/check-contract-change.ps1"`

Or:
`powershell -File run-shared.ps1 -Action contract-check`

Before API changes, review:
- `../Context Repository/standards/api-change-policy.md`
- `../Context Repository/workflows/api-change-workflow.md`

# Test suite

Run from the repository root after installing `requirements.txt` and
`pytest pytest-asyncio pytest-cov ruff`:

```sh
python -m pytest backend/tests -q
python -m ruff check backend --select=E9,F63,F7,F82
```

Frontend checks run from `frontend/` after `npm ci`:

```sh
npm run lint
npm test
npm run build
```

## Fixtures and isolation

- Backend database fixtures use temporary files or in-memory SQLite. The shared
  fixture seeds test user `1`; model constructors and service calls must pass
  `owner_user_id` explicitly. Production service methods are not wrapped to
  accommodate old signatures.
- Shared fixtures register the real application services and reset LLM request
  context for each test. Fixed dummy LLM settings keep the tests independent of
  a developer's `.env` and credentials. Mock LLM calls at the external-call boundary.
- UI tests that render components with asynchronous effects use
  `frontend/src/tests/renderWithEffects.tsx`. Await rendering, rerendering and
  asynchronous actions before checking their results. Use virtual timers for
  polling instead of waiting in real time.

## PostgreSQL

`test_postgresql_schema_bootstrap_actual` requires `TEST_POSTGRES_URL` pointing
to a dedicated disposable PostgreSQL database. It drops and recreates the
application tables. CI supplies that database through its PostgreSQL service;
local runs skip this one integration test when the variable is absent.

## API snapshot

`contracts/openapi_snapshot.json` is a reviewed contract and must be committed.
The test fails if it is missing or differs from the current schema. A mismatch
writes `openapi_snapshot.new.json` for inspection; review the changes before
updating the committed snapshot. The generated comparison file stays ignored.

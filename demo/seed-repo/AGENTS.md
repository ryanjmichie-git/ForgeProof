# Todo API — Agent Instructions

## Project Overview
Simple FastAPI-based Todo REST API with in-memory storage.

## Code Conventions
- Python 3.11+, type hints everywhere
- FastAPI for HTTP, Pydantic for request/response models
- Service layer pattern: routes delegate to `src/services/`
- Tests use `fastapi.testclient.TestClient` and plain pytest (no mocks)
- Each new feature should have corresponding tests in `tests/`

## File Structure
- `src/api/routes.py` — all API routes
- `src/services/` — business logic
- `src/models/` — data models
- `tests/` — pytest tests

## Rules
- Never modify `.gitlab-ci.yml` or `.env*` files
- Keep dependencies minimal
- All new endpoints must have tests

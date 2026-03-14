# Add CSV export endpoint to the Todo API

## Description
We need a new endpoint `GET /todos/export.csv` that exports all todo items as a CSV file. This will allow users to download their todos for offline use or importing into spreadsheets.

## Acceptance Criteria
- The endpoint `GET /todos/export.csv` returns a CSV response with `Content-Type: text/csv`
- The CSV includes a header row: `id,title,completed,created_at`
- Each todo item is one row in the CSV
- Completed status is represented as `true` or `false`
- The response includes a `Content-Disposition` header for download: `attachment; filename="todos.csv"`
- Empty todo list returns just the header row
- The endpoint follows the same authentication pattern as other endpoints

## Non-Goals
- Filtering or pagination for the export
- Import from CSV
- Other export formats (JSON export already exists via the API)

## Suggested Files
- `src/api/routes.py` — add the new route
- `src/services/export_service.py` — CSV generation logic
- `tests/test_export.py` — tests for the new endpoint

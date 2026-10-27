# Operational-queues

Self-hosted web app for planning and viewing operational queues: an admin fills a weekly schedule of large and small operations, and users see the published schedule week by week.

## Pages

| Page | Path | Access |
|:---|:---:|:---:|
| User schedule | `/frontend/user/index.html` | Public, read-only |
| Admin | `/frontend/admin/index.html` | PIN |

## Features

- Weekly schedule with day-by-day records for large and small operations
- Multiple records per day: adding a record for an existing day appends a new entry instead of overwriting it
- Multi-line values: operation descriptions are entered in `textarea` fields and keep their line breaks in the table
- Edit and delete every record from the admin screen (`PUT` / `DELETE` by record id)
- Date column merged per day (`rowspan`), with a compact actions column
- Pin-role selector styled like the buttons
- Week navigation with a week picker and previous / next controls

## Architecture

- **Backend** (`backend/`): FastAPI and Uvicorn, PIN-based auth, JSON state in `data/state.json` written atomically. Runs on Python 3.11.
  - `backend/app/main.py` — app factory and static mounts
  - `backend/app/routes.py` — schedule, admin records and pin endpoints
  - `backend/app/records.py` — record CRUD (`list_records`, `add_record`, `update_record`, `delete_record`)
  - `backend/app/store.py` — state persistence
  - `backend/app/auth.py` — PIN hashing and sessions
- **Frontend** (`frontend/`): plain HTML, CSS and vanilla JavaScript, no build step.
  - `frontend/shared/schedule.js` — `escapeHtml` and `renderWeeks(container, records, weekStartIso, { editable })`
  - `frontend/shared/api.js` — `createRecord`, `updateRecord`, `deleteRecord`, schedule fetch
  - `frontend/shared/style.css` — shared styles (tables, forms, buttons, pin-role)
  - `frontend/admin/` — admin form and editable schedule table
  - `frontend/user/` — read-only schedule view

## API

- `GET /api/schedule` — `{ weeks: [...], records: [...] }` for the requested week
- `POST /api/admin/records` — add a new record (always appends)
- `PUT /api/admin/records/{id}` — update a record
- `DELETE /api/admin/records/{id}` — delete a record

## Getting started

Requires Python 3.11.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Then open `http://127.0.0.1:8000/frontend/user/index.html` and `http://127.0.0.1:8000/frontend/admin/index.html`.

## Testing

```bash
venv\Scripts\python -m pytest backend/tests -v
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

Released under the [Apache License 2.0](LICENSE).

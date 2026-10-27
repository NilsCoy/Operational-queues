<div align="center">

# Operational queues

[![License](https://img.shields.io/badge/License-Apache%202.0-8a8478?style=for-the-badge&labelColor=1f1b16)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-ff6a1a?style=for-the-badge&labelColor=1f1b16)](pyproject.toml)

Self-hosted web app for planning and viewing operational queues: an admin fills a weekly schedule of large and small operations, and users see the published schedule week by week.

---


## Based on [NextUp](https://github.com/DevBytAmir/nextup)

NextUp runs a shared queue for any walk-up service line: one screen issues sequential numbers, any number of counters serve customers from that single line, a TV or monitor shows live queue status with an optional beep or spoken announcement, and an admin screen gives full manual control.

## Pages

| Page |   Path   |          Access          |
|:---|:--------:|:------------------------:|
| User schedule | `/user`  |        read-only         |
| Admin | `/admin` | Create users, add planes |

</div>

## Features

- Weekly schedule with day-by-day records for large and small operations
- Multiple records per day: adding a record for an existing day appends a new entry instead of overwriting it
- Multi-line values: operation descriptions are entered in `textarea` fields and keep their line breaks in the table
- Edit and delete every record from the admin screen (`PUT` / `DELETE` by record id)
- Date column merged per day (`rowspan`), with a compact actions column
- password-role selector styled like the buttons
- Week navigation with a week picker and previous / next controls

## Architecture

- **Backend** (`backend/`): FastAPI and Uvicorn, password-based auth, JSON state in `data/state.json` written atomically. Runs on Python 3.11.
  - `backend/app/main.py` — app factory and static mounts
  - `backend/app/routes.py` — schedule, admin records and password endpoints
  - `backend/app/records.py` — record CRUD (`list_records`, `add_record`, `update_record`, `delete_record`)
  - `backend/app/store.py` — state persistence
  - `backend/app/auth.py` — password hashing and sessions
- **Frontend** (`frontend/`): plain HTML, CSS and vanilla JavaScript, no build step.
  - `frontend/shared/schedule.js` — `escapeHtml` and `renderWeeks(container, records, weekStartIso, { editable })`
  - `frontend/shared/api.js` — `createRecord`, `updateRecord`, `deleteRecord`, schedule fetch
  - `frontend/shared/style.css` — shared styles (tables, forms, buttons, password-role)
  - `frontend/admin/` — admin form and editable schedule table
  - `frontend/user/` — read-only schedule view

## API

- `GET /api/schedule` — `{ weeks: [...], records: [...] }` for the requested week
- `POST /api/admin/records` — add a new record (always appends)
- `PUT /api/admin/records/{id}` — update a record
- `DELETE /api/admin/records/{id}` — delete a record

## Getting started

Requires Python 3.11.

In the Makefile, configure the ip and port

```bash
make install
make reload
```

Then open `http://127.0.0.1:8000/user` or `http://127.0.0.1:8000/admin`.

## Testing

```bash
make test
make lint
make format
```

## License

Released under the [Apache License 2.0](LICENSE).

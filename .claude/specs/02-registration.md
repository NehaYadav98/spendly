# Spec: Registration

## Overview
Make the existing sign-up page work so a visitor can create a Spendly account. `GET /register` already renders the form, but the form posts to a route that only accepts GET, so nothing can be submitted. This step adds the POST handling, input validation and a database helper that stores the new user with a hashed password. Login and sessions depend on real user accounts, so this comes right after the database setup and before Step 3.

## Depends on
- Step 1 (Database setup): `users` table, `get_db()`, `init_db()`

## Routes
- GET /register - render the sign-up form (already exists, behaviour unchanged) - public
- POST /register - validate input, create the user, redirect to `/login` - public

Both methods share the existing `register()` view function in `app.py`.

### POST /register behaviour
| Case | Response |
| --- | --- |
| Valid input | Create user, `302` redirect to `url_for('login')` |
| Name empty after trimming | `400`, re-render form with an error |
| Email lacks text on both sides of `@` | `400`, re-render form with an error |
| Password shorter than 8 characters | `400`, re-render form with an error |
| Email already registered | `400`, re-render form with an error |

- Trim `name` and `email`. Convert `email` to lowercase before validating and storing, so `A@x.com` and `a@x.com` count as the same account.
- Do not trim or otherwise change the password.
- Validation failures use the template's existing `error` variable, not `abort()`, because the user needs to correct the form.

## Database changes
No database changes. The `users` table in `database/db.py` already has `name`, `email` (UNIQUE), `password_hash` and `created_at`.

Add one helper to `database/db.py`:

- `create_user(name, email, password)`
  - Hashes the password with `generate_password_hash` (already imported)
  - Inserts the row with a parameterised query
  - Returns the new user's id
  - Catches `sqlite3.IntegrityError` and returns `None` when the email is taken
  - Closes the connection in `finally`, matching `seed_db()`

Detect duplicates from the UNIQUE constraint rather than a prior `SELECT`, so two simultaneous sign-ups cannot both pass the check.

## Templates
- Create: none
- Modify: `templates/register.html`
  - Change `action="/register"` to `action="{{ url_for('register') }}"`
  - Keep entered values after an error with `value="{{ request.form.get('name', '') }}"` on name, and the same for email. Never refill the password.
  - Add `minlength="8"` to the password input
  - Replace the invalid email placeholder `neha@123` with `you@example.com`

## Files to change
Paths are relative to the app folder `expense-tracker/`, except `CLAUDE.md`, which is at the repo root.

- `app.py`: accept GET and POST on `/register`, add validation, import `create_user`, `redirect`, `request` and `url_for`
- `database/db.py`: add `create_user()`
- `templates/register.html`: changes listed above
- `CLAUDE.md`: change the route table entry to `GET, POST /register`

## Files to create
- `conftest.py` (in `expense-tracker/`): an `app` fixture that points `database.db.DB_PATH` at a temporary file with `monkeypatch` and calls `init_db()`, so tests never touch the real database. Its location also puts `app.py` on the import path for plain `pytest`.
- `tests/test_registration.py`: the cases in the behaviour table, plus a check that the stored password is hashed

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables, never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py`, never in the route
- No new CSS file: the `.auth-error` and `.form-*` styles already exist in `style.css`
- Do not add sessions, `SECRET_KEY`, `flash()` or auto-login. These belong to Step 3.
- Do not implement `/login` POST, `/logout` or any other stub route
- Keep the app on port 5001

## Definition of done
- [ ] `GET /register` shows the form
- [ ] Submitting valid details redirects to `/login`
- [ ] The new row exists in `users`, and `password_hash` is a werkzeug hash, not the plain password
- [ ] Submitting a registered email (including `DEMO@spendly.com` in different case) shows an error and adds no row
- [ ] A blank name, an email without text on both sides of `@`, or a password under 8 characters shows an error and adds no row, even with browser validation bypassed
- [ ] After an error, name and email stay filled in and the password is empty
- [ ] `register.html` has no hardcoded internal URLs
- [ ] `pytest` passes and leaves `expense_tracker.db` unchanged
- [ ] `python app.py` starts on port 5001 without errors

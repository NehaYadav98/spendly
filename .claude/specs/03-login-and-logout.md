# Spec: Login and Logout

## Overview
Let a registered user sign in and out of Spendly. `GET /login` already renders the form, but the form posts to a route that only accepts GET, and `/logout` is a stub. This step adds POST handling for login, a database helper that checks credentials, Flask's signed-cookie session, and a working logout. The profile page and expense pages (Step 4 onward) need to know who the current user is, so sessions come right after registration.

## Depends on
- Step 1 (Database setup): `users` table, `get_db()`, seeded demo user
- Step 2 (Registration): `create_user()`, lowercase email storage, `conftest.py`

## Routes
- GET /login - render the sign-in form (already exists, behaviour unchanged) - public
- POST /login - check credentials, start the session, redirect to `/` - public
- GET /logout - clear the session, redirect to `/` (replaces the stub) - public

GET and POST /login share the existing `login()` view function in `app.py`. `/logout` stays GET to match the route table in `CLAUDE.md`.

### POST /login behaviour
| Case | Response |
| --- | --- |
| Correct email and password | Start session, `302` redirect to `url_for('landing')` |
| Email not registered | `401`, re-render form with `Invalid email or password.` |
| Wrong password | `401`, re-render form with the same message |
| Blank email or password | `401`, re-render form with the same message |

- Trim `email` and convert it to lowercase before the lookup, matching registration, so `DEMO@spendly.com` signs in.
- Do not trim or otherwise change the password.
- Do not apply the 8-character password rule at login. The seeded demo password `demo123` is 7 characters and must still work.
- Use one error message for every failure, so the form does not reveal which emails are registered.
- Validation failures use the template's existing `error` variable, not `abort()`, because the user needs to correct the form.

### Session behaviour
- On success, call `session.clear()`, then set `session["user_id"]`. Clearing first drops anything from a previous session.
- Store only `user_id` in the session.
- `/logout` calls `session.clear()` and redirects to `url_for('landing')`. It works the same when nobody is signed in.

### Secret key
Set near the top of `app.py`, right after `app = Flask(__name__)`:

```python
# Random fallback keeps a real key out of the repo; set SECRET_KEY so sessions survive restarts.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
```

Without `SECRET_KEY` set, restarting the dev server signs everyone out. That is expected.

## Database changes
No database changes. The `users` table in `database/db.py` already has `email` (UNIQUE) and `password_hash`.

Add one helper to `database/db.py`:

- `authenticate_user(email, password)`
  - Selects the user by email with a parameterised query
  - Checks the password with `check_password_hash` (add to the existing werkzeug import)
  - Returns the user row on success, or `None` for an unknown email or wrong password
  - Closes the connection in `finally`, matching `create_user()`

## Templates
- Create: none
- Modify: `templates/login.html`
  - Change `action="/login"` to `action="{{ url_for('login') }}"`
  - Keep the entered email after an error with `value="{{ request.form.get('email', '') }}"`. Never refill the password.
- Modify: `templates/base.html`
  - In `.nav-links`, wrap the links in `{% if session.get('user_id') %}`
  - Signed in: show one `Sign out` link to `url_for('logout')`
  - Signed out: show the current `Sign in` and `Get started` links

## Files to change
Paths are relative to the app folder `expense-tracker/`, except `CLAUDE.md`, which is at the repo root.

- `app.py`: set `secret_key`, accept GET and POST on `/login`, implement `logout()`, import `os`, `secrets`, `session` and `authenticate_user`
- `database/db.py`: add `authenticate_user()`, import `check_password_hash`
- `templates/login.html`: changes listed above
- `templates/base.html`: changes listed above
- `CLAUDE.md`: change the route table to `GET, POST /login` and mark `GET /logout` as implemented

## Files to create
- `tests/test_login.py`, using the existing `app` fixture from `conftest.py`:
  - Each case in the behaviour table
  - A successful login sets `user_id` in the session, and a failed one does not
  - Mixed-case email signs in
  - A password under 8 characters signs in if it is correct (the demo user rule)
  - `/logout` clears the session and redirects to `/`, both signed in and signed out
  - The nav shows `Sign out` only when signed in

The fixture does not run `seed_db()`, so tests create their user with `create_user()`, or insert a row directly for the short-password case.

## New dependencies
No new dependencies. `os` and `secrets` are in the standard library.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables, never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py`, never in the route
- Never commit a real secret key
- No new CSS file: the `.auth-error` and `.form-*` styles already exist in `style.css`
- Do not add a `next` redirect parameter, "remember me", password reset, rate limiting or `flash()`
- Do not add a login-required decorator or protect any route. No route needs it until Step 4.
- Do not implement `/profile` or any other stub route. Redirect to the landing page because `/profile` is still a stub with no nav, so there would be no way to sign out from it.
- Keep the app on port 5001

## Definition of done
- [ ] `GET /login` shows the form
- [ ] Signing in as `demo@spendly.com` with password `demo123` redirects to `/`, and the nav shows `Sign out`
- [ ] Signing in as `DEMO@spendly.com` also works
- [ ] A user created through `/register` can sign in with their password
- [ ] A wrong password, an unregistered email and a blank field each show `Invalid email or password.` and leave the user signed out, even with browser validation bypassed
- [ ] After an error, the email stays filled in and the password is empty
- [ ] Clicking `Sign out` redirects to `/`, and the nav shows `Sign in` and `Get started` again
- [ ] Visiting `/logout` while signed out redirects to `/` without an error
- [ ] The session cookie survives moving between pages while signed in
- [ ] `login.html` and `base.html` have no hardcoded internal URLs
- [ ] `pytest` passes and leaves `expense_tracker.db` unchanged
- [ ] `python app.py` starts on port 5001 without errors

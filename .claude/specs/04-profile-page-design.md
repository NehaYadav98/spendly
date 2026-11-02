# Spec: Profile Page Design

## Overview
Give a signed-in user one page that shows who they are and where their money went: an identity card, three summary stats, their latest transactions and spending by category. Later expense steps (7 to 9) will feed this page, so it comes straight after login and before them.

This document describes the design as built, in the same way as the Step 3 spec. The page reads real data through `database/db.py`. It replaces the earlier draft, which asked for hardcoded data. Wiring the page to the database is therefore already done, so the planned Step 5 needs re-scoping.

## Depends on
- Step 1 (Database setup): `users` and `expenses` tables, `get_db()`
- Step 2 (Registration): real user accounts, `conftest.py`
- Step 3 (Login and Logout): `session["user_id"]`, `enforce_session()`, the toast in `base.html`

## Routes
- GET /profile - render the profile page - logged-in

No per-route login check: `profile` is not in `PUBLIC_ENDPOINTS`, so `enforce_session()` redirects signed-out visitors to `/login`. A session whose user row is missing gets `abort(404)`.

`/profile/edit` already exists but is not part of this spec. See "Not in this step".

## Database changes
No database changes. The existing `users` and `expenses` tables are enough.

The page uses these read helpers in `database/db.py`. Each one filters by `user_id`:

| Helper | Returns |
| --- | --- |
| `get_user_by_id(user_id)` | `id`, `name`, `email`, `created_at`, and never `password_hash` |
| `get_expense_summary(user_id)` | `total`, `count`, `top_category` (`None` with no expenses) |
| `get_expenses(user_id)` | All rows, by date descending, then id descending |
| `get_spending_by_category(user_id)` | Category totals, highest first, ties alphabetical |

## Templates
- Create: `templates/profile.html`, extending `base.html` and loading `css/profile.css` through `{% block head %}`
- Modify: `templates/base.html`, adding a `Profile` nav link with `class="nav-profile"` for signed-in users, inside a `nav_user` block that `profile.html` overrides with the user's name

### Layout
Centred at 92% of the window width, with the navbar content at the same width and a `14px` gap between parts. The navbar is `40px` high. The identity card is full width and at least `102px` high, then three equal stat cards in one row. Below them, Recent Transactions (68%) and By Category (32%) sit side by side. They stack at 900px and narrower.

| Part | Content | Empty state |
| --- | --- | --- |
| Identity card | Avatar, name, email, `Member since March 2025` | Not applicable |
| Stats row | Total spent, Transactions, Top category | `₹0.00`, `0`, `None yet` |
| Recent Transactions | Date, Description, Category badge, Amount | `No transactions yet.` with no table |
| By Category | Name and amount on one line, bar below | `No spending to show yet.` |

- **Avatar:** first letter of the first and last words of the name, uppercase, or one letter for a single-word name. It is `aria-hidden` because the name sits beside it.
- **Dates:** `09 Mar 2026`, through the `short_date` filter.
- **Missing description:** shows `—`.
- **Bars:** each width is the category's share of total spending, with a `4px` minimum so small shares stay visible. The exact percentage is in the row's `title`.
- **Zero spending:** the category section shows its empty message when the total is 0, which also prevents dividing by zero.

### Visual rules
- **Cards:** `--paper-card` background, `1px` `--border` border, `--radius-md` (`9px`) corners, soft shadow, `1rem 1.25rem` padding
- **Spacing and sizes:** compact, with `13px` table and category text, `11px` labels, `18px` card titles, `20px` name and stat values up to `28px`
- **Bar colours:** Shopping brown/gold, Other grey, Food dark green, Bills blue-grey, Health red, Entertainment purple, Transport blue, as `--bar-*` tokens and `fill-*` classes. Any other category uses `--accent`. The unfilled track is light grey.
- **Table:** a divider under the Recent Transactions heading, separators between rows and a highlight on row hover
- **Type:** bold `--font-display` for the name, stat values and card titles. `--font-body` for navigation, labels and table content. Uppercase muted labels for stats, which sit above their values, and table headers.
- **Numbers:** table and category amounts are right-aligned with `tabular-nums`
- **Badges:** one pill per category with its own background and text colour tokens: Food, Transport, Bills, Health, Entertainment and Shopping. Any other category, including `Other`, uses the default grey.
- **Palette:** `profile.css` sets background `#f7f7f7`, cards `#ffffff`, green `#174c35`, text `#111111`, secondary text `#777777` and border `#e5e5e5` as tokens in `:root`. It loads on this page only, so the navbar, footer and toast take these colours here and nowhere else.
- **Navbar on this page:** the user's name replaces the `Profile` link, shortened with an ellipsis if long, and `Sign out` appears as plain text. Other pages keep `Profile` and `Sign out`, so no per-request user lookup is needed.

### Phones (600px and narrower)
- Stats stack in one column
- Each transaction becomes two lines: description and amount, then date and badge
- The table's `role` attributes stay, so it is still announced as a table after its `display` changes

## Files to change
Paths are relative to the app folder `expense-tracker/`, except `CLAUDE.md`, which is at the repo root.

- `app.py`: real `profile()` view and the `short_date` template filter
- `database/db.py`: the read helpers listed above
- `templates/base.html`: `Profile` nav link inside the `nav_user` block
- `static/css/style.css`: keep `.nav-profile` visible at 600px and narrower, and reduce the navbar's side padding there
- `CLAUDE.md`: mark `GET /profile` as implemented

## Files to create
- `templates/profile.html`
- `static/css/profile.css`
- `tests/test_profile.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes on this page)
- Use CSS variables, never hardcode hex values. Hex values appear only where tokens are defined in `:root`.
- All templates extend `base.html`
- DB logic stays in `database/db.py`, and the route only fetches and renders
- Page-specific styles stay in `profile.css`, which must not load on other pages
- No inline styles, with one exception: each bar's computed `width`, because it comes from the data
- Category badges use CSS classes, not inline colours
- All amounts use `₹`, never `$`
- `url_for()` for every internal link
- No JavaScript, chart library or icon library: the bars are plain HTML and CSS
- Do not implement the `/expenses/*` stubs
- Keep the app on port 5001

### Not in this step
- **Edit link:** the page has no link to `/profile/edit`, and `tests/test_profile.py` asserts that `Edit Profile` is absent. The edit form is therefore reachable only by typing its URL.
- **Editing itself:** `/profile/edit` and `edit_profile.html` are built but have no spec of their own.
- **Indian digit grouping:** amounts use `₹1,234,567.00`, not `₹12,34,567.00`.
- **Paging:** the page shows every transaction, with no paging, so a long history makes a long page.
- **Date filtering:** totals cover all time.

## Definition of done
- [ ] Visiting `/profile` while signed out redirects to `/login`
- [ ] Signing in as `demo@spendly.com` with password `demo123` and opening `/profile` returns 200 with the name, email and member-since date
- [ ] The avatar shows `DU` for the demo user
- [ ] The three stats match the user's expenses, and all amounts show `₹`
- [ ] Recent Transactions shows every transaction, newest first, with coloured category badges
- [ ] By Category is sorted highest first, and bar widths and colours match each category
- [ ] The navbar is `40px` high, the identity card `102px` for a short name, and the content 92% of the window width with `14px` gaps and `9px` card corners
- [ ] Above 900px, Recent Transactions and By Category sit side by side at roughly 68% and 32%, and they stack at 900px and narrower
- [ ] A new user with no expenses sees `₹0.00`, `0`, `None yet` and both empty messages, with no error
- [ ] Another user's expenses never appear
- [ ] A name or description containing HTML is shown as text, not run
- [ ] At 600px and narrower, stats stack, transactions take two lines, and the page does not scroll sideways
- [ ] The `Profile` link shows in the nav on other pages when signed in, and `/profile` shows the user's name and `Sign out` instead
- [ ] `css/profile.css` loads on `/profile` only
- [ ] `profile.html` has no hardcoded internal URLs or hex values
- [ ] `pytest tests/test_profile.py -v` passes
- [ ] `python app.py` starts on port 5001 without errors

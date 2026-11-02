import pytest

from database.db import create_user, get_db, get_recent_expenses, get_user_by_id

EMAIL = "asha@example.com"
PASSWORD = "secret-pass"
SAVED_MESSAGE = b"Your profile has been updated."


@pytest.fixture
def user_id(client):
    return create_user("Asha Rao", EMAIL, PASSWORD)


@pytest.fixture
def signed_in(client, user_id):
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    return client


def add_expense(user_id, amount, category, date="2026-01-01", description=None):
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, date, description),
            )
    finally:
        conn.close()


def save(client, **overrides):
    data = {"name": "Asha Rao", "email": EMAIL, "current_password": "", **overrides}
    return client.post("/profile/edit", data=data)


# ------------------------------------------------------------------ #
# Viewing                                                             #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("path", ["/profile", "/profile/edit"])
def test_signed_out_get_redirects_to_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_signed_out_post_redirects_and_changes_nothing(client, user_id):
    response = save(client, name="Hacked")
    assert response.headers["Location"].endswith("/login")
    assert get_user_by_id(user_id)["name"] == "Asha Rao"


def test_profile_shows_user_details(signed_in, user_id):
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET created_at = '2025-03-15 10:00:00' WHERE id = ?", (user_id,))
    conn.close()

    page = signed_in.get("/profile").data.decode()
    assert "Asha Rao" in page
    assert EMAIL in page
    assert "Member since March 2025" in page
    assert 'aria-hidden="true">AR<' in page
    assert "Edit Profile" not in page
    assert "Back to home" not in page
    assert "coming in Step 4" not in page


def test_profile_never_exposes_password_hash(signed_in, user_id):
    assert "password_hash" not in get_user_by_id(user_id).keys()
    conn = get_db()
    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    conn.close()
    for path in ["/profile", "/profile/edit"]:
        assert stored.encode() not in signed_in.get(path).data


def test_summary_with_expenses(signed_in, user_id):
    add_expense(user_id, 1500.50, "Bills")
    add_expense(user_id, 100, "Food")
    add_expense(user_id, 100, "Food")
    page = signed_in.get("/profile").data.decode()
    assert "₹1,700.50" in page
    assert "<dd>3</dd>" in page
    assert "<dd>Bills</dd>" in page
    assert "$" not in page


def test_top_category_tie_goes_to_first_alphabetically(signed_in, user_id):
    add_expense(user_id, 100, "Food")
    add_expense(user_id, 100, "Bills")
    assert "<dd>Bills</dd>" in signed_in.get("/profile").data.decode()


def test_summary_with_no_expenses(signed_in):
    page = signed_in.get("/profile").data.decode()
    assert "₹0.00" in page
    assert "<dd>0</dd>" in page
    assert "None yet" in page


def test_other_users_expenses_are_not_counted(signed_in):
    other_id = create_user("Ravi", "ravi@example.com", PASSWORD)
    add_expense(other_id, 999, "Food")
    page = signed_in.get("/profile").data.decode()
    assert "₹0.00" in page
    assert "Ravi" not in page


def test_name_with_html_is_escaped(client):
    create_user("<script>alert(1)</script>", EMAIL, PASSWORD)
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    page = client.get("/profile").data
    assert b"<script>alert(1)" not in page
    assert b"&lt;script&gt;alert(1)" in page


def test_missing_user_row_is_404(signed_in, monkeypatch):
    monkeypatch.setattr("app.get_user_by_id", lambda _: None)
    assert signed_in.get("/profile").status_code == 404
    assert signed_in.get("/profile/edit").status_code == 404


@pytest.mark.parametrize(
    ("name", "initials"),
    [("Asha", "A"), ("asha rao", "AR"), ("Asha Devi Rao", "AR"), ("  Asha   Rao ", "AR")],
)
def test_avatar_initials(client, name, initials):
    create_user(name, EMAIL, PASSWORD)
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    assert f'aria-hidden="true">{initials}<' in client.get("/profile").data.decode()


def test_recent_transactions_show_latest_five_newest_first(signed_in, user_id):
    for day in range(1, 7):
        add_expense(user_id, day * 100, "Food", f"2026-03-0{day}", f"Item {day}")
    page = signed_in.get("/profile").data.decode()
    positions = [page.index(f"Item {day}") for day in [6, 5, 4, 3, 2]]
    assert positions == sorted(positions)
    assert "Item 1" not in page
    assert "<dd>6</dd>" in page


def test_same_day_transactions_show_newest_added_first(signed_in, user_id):
    add_expense(user_id, 1, "Food", "2026-03-01", "First")
    add_expense(user_id, 2, "Food", "2026-03-01", "Second")
    assert [row["description"] for row in get_recent_expenses(user_id)] == ["Second", "First"]


def test_transaction_row_contents(signed_in, user_id):
    add_expense(user_id, 1234.5, "Bills", "2026-03-09", "Electricity")
    page = signed_in.get("/profile").data.decode()
    assert "09 Mar 2026" in page
    assert "Electricity" in page
    assert '<span class="profile-badge badge-bills">Bills</span>' in page
    assert '<td role="cell" class="cell-amount">₹1,234.50</td>' in page


def test_transaction_without_description_shows_dash(signed_in, user_id):
    add_expense(user_id, 50, "Other")
    assert '<td role="cell" class="cell-description">—</td>' in signed_in.get("/profile").data.decode()


def test_no_transactions_shows_empty_message(signed_in):
    page = signed_in.get("/profile").data.decode()
    assert "No transactions yet." in page
    assert "<table" not in page


def test_other_users_transactions_are_not_listed(signed_in):
    other_id = create_user("Ravi", "ravi@example.com", PASSWORD)
    add_expense(other_id, 999, "Food", "2026-03-01", "Ravi secret")
    assert "Ravi secret" not in signed_in.get("/profile").data.decode()


def test_description_with_html_is_escaped(signed_in, user_id):
    add_expense(user_id, 1, "Food", "2026-03-01", "<b>bold</b>")
    page = signed_in.get("/profile").data
    assert b"<b>bold</b>" not in page
    assert b"&lt;b&gt;bold" in page


def test_spending_by_category_is_sorted_with_bars_showing_share_of_total(signed_in, user_id):
    add_expense(user_id, 100, "Food")
    add_expense(user_id, 200, "Bills")
    add_expense(user_id, 100, "Bills")
    page = signed_in.get("/profile").data.decode()
    section = page[page.index("Spending by Category"):]
    assert section.index('category-name">Bills') < section.index('category-name">Food')
    assert 'style="width: 75.0%"' in section
    assert 'style="width: 25.0%"' in section
    assert '<span class="category-amount">₹300.00</span>' in section
    assert '<span class="category-amount">₹100.00</span>' in section


def test_spending_by_category_tie_is_alphabetical(signed_in, user_id):
    add_expense(user_id, 100, "Food")
    add_expense(user_id, 100, "Bills")
    section = signed_in.get("/profile").data.decode().split("Spending by Category")[1]
    assert section.index('category-name">Bills') < section.index('category-name">Food')


@pytest.mark.parametrize("amounts", [[], [0, 0]])
def test_spending_by_category_with_nothing_spent_shows_message(signed_in, user_id, amounts):
    for amount in amounts:
        add_expense(user_id, amount, "Food")
    response = signed_in.get("/profile")
    assert response.status_code == 200
    assert "No spending to show yet." in response.data.decode()


def test_spending_by_category_excludes_other_users(signed_in, user_id):
    other_id = create_user("Ravi", "ravi@example.com", PASSWORD)
    add_expense(other_id, 999, "Shopping")
    add_expense(user_id, 50, "Food")
    section = signed_in.get("/profile").data.decode().split("Spending by Category")[1]
    assert 'category-name">Shopping' not in section
    assert 'style="width: 100.0%"' in section


def test_profile_styles_do_not_load_on_other_pages(signed_in):
    assert b"css/profile.css" in signed_in.get("/profile").data
    assert b"css/profile.css" not in signed_in.get("/").data
    assert b"css/profile.css" not in signed_in.get("/profile/edit").data


def test_nav_link_only_when_signed_in(client, user_id):
    assert b'href="/profile"' not in client.get("/").data
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    assert b'href="/profile"' in client.get("/").data


# ------------------------------------------------------------------ #
# Editing                                                             #
# ------------------------------------------------------------------ #

def test_edit_form_is_prefilled(signed_in):
    page = signed_in.get("/profile/edit").data.decode()
    assert 'value="Asha Rao"' in page
    assert f'value="{EMAIL}"' in page
    assert "Save Changes" in page


def test_saving_name_needs_no_password_and_shows_message_once(signed_in, user_id):
    response = save(signed_in, name="  Asha R  ")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert get_user_by_id(user_id)["name"] == "Asha R"

    page = signed_in.get("/profile").data
    assert SAVED_MESSAGE in page
    assert b"Asha R" in page
    assert SAVED_MESSAGE not in signed_in.get("/profile").data


def test_changing_email_with_password_moves_the_login(app, signed_in, user_id):
    response = save(signed_in, email="  NEW@Example.com ", current_password=PASSWORD)
    assert response.status_code == 302
    assert get_user_by_id(user_id)["email"] == "new@example.com"

    fresh = app.test_client()
    assert fresh.post("/login", data={"email": EMAIL, "password": PASSWORD}).status_code == 401
    assert fresh.post("/login", data={"email": "new@example.com", "password": PASSWORD}).status_code == 302


@pytest.mark.parametrize("password", ["", "wrong-pass"])
def test_changing_email_needs_the_right_password(signed_in, user_id, password):
    response = save(signed_in, email="new@example.com", current_password=password)
    assert response.status_code == 400
    assert b"current password" in response.data
    assert get_user_by_id(user_id)["email"] == EMAIL


def test_email_differing_only_by_case_needs_no_password(signed_in, user_id):
    assert save(signed_in, email="ASHA@example.com").status_code == 302
    assert get_user_by_id(user_id)["email"] == EMAIL


def test_taken_email_is_rejected(signed_in, user_id):
    create_user("Ravi", "ravi@example.com", PASSWORD)
    response = save(signed_in, email="ravi@example.com", current_password=PASSWORD)
    assert response.status_code == 400
    assert b"already registered" in response.data
    assert get_user_by_id(user_id)["email"] == EMAIL


def test_taken_email_is_not_revealed_without_the_password(signed_in):
    create_user("Ravi", "ravi@example.com", PASSWORD)
    assert b"already registered" not in save(signed_in, email="ravi@example.com").data


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"name": "   "},
        {"name": "a" * 101},
        {"email": ""},
        {"email": "abc"},
        {"email": "@x.com"},
        {"email": "a@"},
        {"email": "a" * 250 + "@x.com"},
    ],
)
def test_invalid_input_is_rejected(signed_in, user_id, overrides):
    assert save(signed_in, current_password=PASSWORD, **overrides).status_code == 400
    user = get_user_by_id(user_id)
    assert user["name"] == "Asha Rao"
    assert user["email"] == EMAIL


def test_error_keeps_input_but_not_password(signed_in):
    response = save(signed_in, name="", email="typed@example.com", current_password="typed-secret")
    assert b"typed@example.com" in response.data
    assert b"typed-secret" not in response.data


def test_edit_only_changes_the_signed_in_user(signed_in):
    other_id = create_user("Ravi", "ravi@example.com", PASSWORD)
    save(signed_in, name="Asha R", user_id=other_id, id=other_id)
    assert get_user_by_id(other_id)["name"] == "Ravi"


def test_session_cookie_is_samesite_lax(client, user_id):
    response = client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    assert "SameSite=Lax" in response.headers["Set-Cookie"]

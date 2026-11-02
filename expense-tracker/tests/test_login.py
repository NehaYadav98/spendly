import pytest

from database.db import create_session, create_user, delete_session, get_db, is_session_active

EMAIL = "asha@example.com"
PASSWORD = "secret-pass"


@pytest.fixture
def user_id(client):
    return create_user("Asha Rao", EMAIL, PASSWORD)


def session_user_id(client):
    with client.session_transaction() as session:
        return session.get("user_id")


def sign_in(client, email=EMAIL, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def test_get_shows_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_correct_credentials_start_session_and_redirect_home(client, user_id):
    response = sign_in(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert session_user_id(client) == user_id


def test_mixed_case_padded_email_signs_in(client, user_id):
    assert sign_in(client, email="  ASHA@Example.COM ").status_code == 302
    assert session_user_id(client) == user_id


def test_seven_character_password_signs_in(client):
    new_id = create_user("Demo", "demo@example.com", "demo123")
    assert sign_in(client, "demo@example.com", "demo123").status_code == 302
    assert session_user_id(client) == new_id


def test_registered_user_can_sign_in(client):
    client.post("/register", data={"name": "Asha", "email": EMAIL, "password": PASSWORD})
    assert sign_in(client).status_code == 302
    assert session_user_id(client) is not None


@pytest.mark.parametrize(
    "data",
    [
        {"email": EMAIL, "password": "wrong-pass"},
        {"email": "nobody@example.com", "password": PASSWORD},
        {"email": "", "password": PASSWORD},
        {"email": EMAIL, "password": ""},
        {},
    ],
    ids=["wrong-password", "unknown-email", "blank-email", "blank-password", "empty-form"],
)
def test_bad_credentials_are_rejected(client, user_id, data):
    response = client.post("/login", data=data)
    assert response.status_code == 401
    assert b"Invalid email or password." in response.data
    assert session_user_id(client) is None


def test_password_is_not_trimmed(client, user_id):
    assert sign_in(client, password=f" {PASSWORD} ").status_code == 401


def test_error_keeps_email_but_not_password(client, user_id):
    response = sign_in(client, password="wrong-pass")
    assert EMAIL.encode() in response.data
    assert b"wrong-pass" not in response.data


def test_logout_when_signed_in_clears_session(client, user_id):
    sign_in(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert session_user_id(client) is None


def test_logout_when_signed_out_redirects(client):
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


LOGOUT_MESSAGE = b"You have been logged out successfully!"
PROTECTED = ["/profile", "/expenses/add", "/expenses/1/edit", "/expenses/1/delete"]


def test_logout_message_shows_once(client, user_id):
    sign_in(client)
    assert LOGOUT_MESSAGE not in client.get("/").data
    assert LOGOUT_MESSAGE in client.get("/logout", follow_redirects=True).data
    assert LOGOUT_MESSAGE not in client.get("/").data


def test_logout_when_signed_out_shows_no_message(client):
    assert LOGOUT_MESSAGE not in client.get("/logout", follow_redirects=True).data


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_page_redirects_to_login_when_signed_out(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_page_is_blocked_after_logout(client, user_id, path):
    sign_in(client)
    assert client.get(path).status_code == 200
    client.get("/logout")
    assert client.get(path).headers["Location"].endswith("/login")


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/terms", "/privacy", "/static/css/style.css"])
def test_public_pages_stay_open_when_signed_out(client, path):
    assert client.get(path).status_code == 200


def test_unknown_url_is_still_404_when_signed_out(client):
    assert client.get("/no-such-page").status_code == 404


def test_pages_are_not_cached_but_static_files_can_be(client):
    assert client.get("/").headers["Cache-Control"] == "no-store"
    assert client.get("/static/css/style.css").headers.get("Cache-Control") != "no-store"


def browser_with_cookie_from(app, client):
    other = app.test_client()
    other.set_cookie("session", client.get_cookie("session").value)
    return other


def assert_signed_out(browser):
    response = browser.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert b"Sign out" not in browser.get("/").data


def test_cookie_from_before_logout_cannot_be_reused(app, client, user_id):
    sign_in(client)
    copy = browser_with_cookie_from(app, client)
    assert copy.get("/profile").status_code == 200

    client.get("/logout")

    assert_signed_out(copy)


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_guest_pages_redirect_home_when_signed_in(client, user_id, path):
    sign_in(client)
    response = client.get(path)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_login_post_when_signed_in_starts_no_new_session(client, user_id):
    sign_in(client)
    response = sign_in(client)
    assert response.status_code == 302
    assert len(stored_sessions()) == 1


def test_register_post_when_signed_in_creates_no_user(client, user_id):
    sign_in(client)
    response = client.post(
        "/register", data={"name": "New", "email": "new@example.com", "password": PASSWORD}
    )
    assert response.status_code == 302
    conn = get_db()
    try:
        assert conn.execute("SELECT 1 FROM users WHERE email = 'new@example.com'").fetchone() is None
    finally:
        conn.close()


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_guest_pages_open_again_after_logout(client, user_id, path):
    sign_in(client)
    client.get("/logout")
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_guest_pages_open_with_a_dead_session_cookie(app, client, user_id, path):
    sign_in(client)
    copy = browser_with_cookie_from(app, client)
    client.get("/logout")
    assert copy.get(path).status_code == 200


def test_replayed_logout_shows_no_message(app, client, user_id):
    sign_in(client)
    copy = browser_with_cookie_from(app, client)
    client.get("/logout")
    assert LOGOUT_MESSAGE not in copy.get("/logout", follow_redirects=True).data


def test_logout_only_ends_that_session(app, client, user_id):
    other_device = app.test_client()
    sign_in(client)
    sign_in(other_device)

    client.get("/logout")

    assert other_device.get("/profile").status_code == 200


def test_signed_cookie_without_a_server_session_is_rejected(client, user_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id
    assert_signed_out(client)
    assert session_user_id(client) is None


def test_session_token_only_works_for_its_own_user(client, user_id):
    other_id = create_user("Other", "other@example.com", PASSWORD)
    with client.session_transaction() as session:
        session["user_id"] = other_id
        session["session_token"] = create_session(user_id)
    assert_signed_out(client)


def stored_sessions():
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM sessions").fetchall()
    finally:
        conn.close()


def test_token_is_stored_hashed_and_removed_on_delete(client, user_id):
    token = create_session(user_id)
    assert is_session_active(token, user_id)
    assert stored_sessions()[0]["token_hash"] != token

    delete_session(token)

    assert not is_session_active(token, user_id)
    assert stored_sessions() == []


def test_logout_removes_the_server_session(client, user_id):
    sign_in(client)
    assert len(stored_sessions()) == 1
    client.get("/logout")
    assert stored_sessions() == []


def test_sessions_past_the_cookie_lifetime_are_purged(client, user_id):
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at) VALUES ('old', ?, datetime('now', '-32 days'))",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at) VALUES ('recent', ?, datetime('now', '-30 days'))",
            (user_id,),
        )
    conn.close()

    create_session(user_id)

    remaining = {row["token_hash"] for row in stored_sessions()}
    assert "old" not in remaining
    assert "recent" in remaining


def test_nav_when_signed_out(client):
    page = client.get("/").data
    assert b"Sign in" in page
    assert b"Get started" in page
    assert b"Sign out" not in page
    assert b"Welcome back!" not in page


def test_nav_when_signed_in(client, user_id):
    sign_in(client)
    page = client.get("/").data
    assert b"Sign out" in page
    assert b"Sign in" not in page
    assert b"Welcome back!" in page

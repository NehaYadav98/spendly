import pytest
from werkzeug.security import check_password_hash

from database.db import get_db

VALID = {"name": "Asha Rao", "email": "asha@example.com", "password": "secret-pass"}


def users():
    conn = get_db()
    try:
        return conn.execute("SELECT * FROM users").fetchall()
    finally:
        conn.close()


def post(client, **overrides):
    return client.post("/register", data={**VALID, **overrides})


def test_get_shows_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


def test_valid_details_create_user_and_redirect_to_login(client):
    response = post(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert [user["name"] for user in users()] == ["Asha Rao"]


def test_password_is_stored_hashed(client):
    post(client)
    stored = users()[0]["password_hash"]
    assert stored != VALID["password"]
    assert check_password_hash(stored, VALID["password"])


def test_email_is_stored_trimmed_and_lowercase(client):
    post(client, email="  Asha@Example.COM ")
    assert users()[0]["email"] == "asha@example.com"


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_is_rejected(client, name):
    assert post(client, name=name).status_code == 400
    assert users() == []


@pytest.mark.parametrize("email", ["", "abc", "@x.com", "a@"])
def test_malformed_email_is_rejected(client, email):
    assert post(client, email=email).status_code == 400
    assert users() == []


def test_missing_fields_are_rejected(client):
    assert client.post("/register", data={}).status_code == 400
    assert users() == []


def test_seven_character_password_is_rejected(client):
    assert post(client, password="a" * 7).status_code == 400
    assert users() == []


def test_eight_character_password_is_accepted(client):
    assert post(client, password="a" * 8).status_code == 302
    assert len(users()) == 1


@pytest.mark.parametrize("email", ["asha@example.com", "ASHA@example.com"])
def test_duplicate_email_is_rejected(client, email):
    post(client)
    response = post(client, email=email)
    assert response.status_code == 400
    assert b"already registered" in response.data
    assert len(users()) == 1


def test_error_keeps_name_and_email_but_not_password(client):
    response = post(client, password="short7!")
    assert b"Asha Rao" in response.data
    assert b"asha@example.com" in response.data
    assert b"short7!" not in response.data

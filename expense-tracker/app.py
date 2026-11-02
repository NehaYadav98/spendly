import os
import secrets

from flask import Flask, flash, redirect, render_template, request, session, url_for

from database.db import (
    authenticate_user,
    create_session,
    create_user,
    delete_session,
    get_db,
    init_db,
    is_session_active,
    seed_db,
)

app = Flask(__name__)
# Random fallback keeps a real key out of the repo; set SECRET_KEY so sessions survive restarts.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

with app.app_context():
    init_db()
    seed_db()

# Anything not listed requires login, so new pages are protected by default.
PUBLIC_ENDPOINTS = {"landing", "register", "login", "logout", "terms", "privacy", "static"}
GUEST_ONLY_ENDPOINTS = {"register", "login"}


@app.before_request
def enforce_session():
    if request.endpoint == "static":
        return None
    # A correctly signed cookie isn't enough: its session must still exist on the server.
    if "user_id" in session and not is_session_active(session.get("session_token", ""), session["user_id"]):
        session.clear()
    # endpoint is None for unknown URLs, which should stay a 404.
    if request.endpoint and request.endpoint not in PUBLIC_ENDPOINTS and not session.get("user_id"):
        return redirect(url_for("login"))
    if request.endpoint in GUEST_ONLY_ENDPOINTS and session.get("user_id"):
        return redirect(url_for("landing"))


@app.after_request
def disable_page_cache(response):
    # Stops the back button reshowing signed-in pages or the logout message.
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    local_part, _, domain = email.partition("@")

    if not name:
        error = "Please enter your name."
    # shortcut: only checks for text around @, add email verification for a real check.
    elif not (local_part and domain):
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif create_user(name, email, password) is None:
        error = "That email is already registered."
    else:
        return redirect(url_for("login"))

    return render_template("register.html", error=error), 400


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = authenticate_user(email, password)

    if user is None:
        return render_template("login.html", error="Invalid email or password."), 401

    # Clear first so nothing from a previous session carries over.
    session.clear()
    session["user_id"] = user["id"]
    session["session_token"] = create_session(user["id"])
    return redirect(url_for("landing"))


@app.route("/logout")
def logout():
    was_signed_in = session.get("user_id")
    delete_session(session.get("session_token", ""))
    session.clear()
    if was_signed_in:
        flash("You have been logged out successfully!")
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)

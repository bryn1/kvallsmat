"""tests.test_registration — MC 1355.7 open registration (owner-ratified).

POST /api/auth/register: happy path (200 + auto-login session cookie),
duplicate username -> 409, weak/short password -> 422, and the registered
credentials must then work through the normal login path.
"""
from __future__ import annotations

REGISTER = "/api/auth/register"


def test_register_happy_path_sets_session(client):
    r = client.post(REGISTER, json={"username": "anna", "password": "hunter2secret"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "username": "anna"}
    # auto-login: the session cookie must resolve on /api/auth/me
    me = client.get("/api/auth/me", cookies={
        "matapp_session": r.headers["set-cookie"].split(";")[0].split("=")[1]})
    assert me.status_code == 200
    assert me.json()["username"] == "anna"


def test_register_duplicate_username_409(client):
    body = {"username": "dup", "password": "hunter2secret"}
    assert client.post(REGISTER, json=body).status_code == 200
    r = client.post(REGISTER, json=body)
    assert r.status_code == 409
    assert "taken" in r.json()["detail"]


def test_register_weak_password_422(client):
    r = client.post(REGISTER, json={"username": "shorty", "password": "short"})
    assert r.status_code == 422
    assert "password" in r.json()["detail"]


def test_register_blank_username_422(client):
    r = client.post(REGISTER, json={"username": "   ", "password": "hunter2secret"})
    assert r.status_code == 422


def test_registered_credentials_login(client):
    creds = {"username": "loginpath", "password": "hunter2secret"}
    reg = client.post(REGISTER, json=creds)
    assert reg.status_code == 200
    r = client.post("/api/auth/login", json=creds)
    assert r.status_code == 200
    # Secure cookie + http://testserver: replay the Set-Cookie explicitly
    # (same TestClient jar artifact T5 attack 4 documented for login).
    token = r.headers["set-cookie"].split(";")[0].split("=")[1]
    me = client.get("/api/auth/me", cookies={"matapp_session": token})
    assert me.status_code == 200
    assert me.json()["username"] == "loginpath"


def test_register_persists_argon2id_hash(client):
    """The stored password_hash is an argon2id PHC string, never plaintext."""
    from app import db as dbm
    from app.models.users import User

    client.post(REGISTER, json={"username": "hashcheck",
                                "password": "hunter2secret"})
    session = dbm._Session()
    try:
        user = session.query(User).filter_by(username="hashcheck").one()
    finally:
        session.close()
    assert user.password_hash.startswith("$argon2id$")
    assert "hunter2secret" not in user.password_hash

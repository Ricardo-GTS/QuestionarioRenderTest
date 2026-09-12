from tests.conftest import requires_db


def _fake_claims(sub: str, email: str, name: str = "Aluno Google"):
    return {"sub": sub, "email": email, "email_verified": True, "name": name}


@requires_db
def test_google_login_creates_new_user(client, monkeypatch):
    import app.api.routers.auth as auth_router

    monkeypatch.setattr(
        auth_router,
        "verify_google_id_token",
        lambda credential: _fake_claims("google-sub-1", "novo@example.com"),
    )

    resp = client.post("/auth/google", json={"credential": "fake-token"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "novo@example.com"


@requires_db
def test_google_login_is_idempotent_for_same_sub(client, monkeypatch):
    import app.api.routers.auth as auth_router

    monkeypatch.setattr(
        auth_router,
        "verify_google_id_token",
        lambda credential: _fake_claims("google-sub-2", "repetido@example.com"),
    )

    first = client.post("/auth/google", json={"credential": "fake-token"})
    second = client.post("/auth/google", json={"credential": "fake-token"})
    assert first.status_code == 200
    assert second.status_code == 200

    first_me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {first.json()['access_token']}"}
    ).json()
    second_me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {second.json()['access_token']}"}
    ).json()
    assert first_me["id"] == second_me["id"]


@requires_db
def test_google_login_links_existing_account_by_email(client, monkeypatch):
    import app.api.routers.auth as auth_router

    resp = client.post(
        "/auth/register",
        json={"name": "Ja Cadastrado", "email": "existente@example.com", "password": "senha1234"},
    )
    assert resp.status_code == 201
    existing_id = resp.json()["id"]

    monkeypatch.setattr(
        auth_router,
        "verify_google_id_token",
        lambda credential: _fake_claims("google-sub-3", "existente@example.com"),
    )
    resp = client.post("/auth/google", json={"credential": "fake-token"})
    assert resp.status_code == 200

    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"}
    ).json()
    assert me["id"] == existing_id

    # a senha original continua valendo -- login por Google so complementa, nao substitui
    resp = client.post("/auth/login", json={"email": "existente@example.com", "password": "senha1234"})
    assert resp.status_code == 200


@requires_db
def test_google_login_rejects_invalid_token(client, monkeypatch):
    import app.api.routers.auth as auth_router

    def _raise(credential):
        raise ValueError("bad token")

    monkeypatch.setattr(auth_router, "verify_google_id_token", _raise)

    resp = client.post("/auth/google", json={"credential": "not-a-real-token"})
    assert resp.status_code == 401

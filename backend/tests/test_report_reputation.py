from tests.conftest import requires_db

ADMIN_EMAIL = "admin@example.com"  # precisa bater com o default de ADMIN_EMAILS em conftest.py


def _register_and_login(client, name: str, email: str) -> dict:
    client.post("/auth/register", json={"name": name, "email": email, "password": "senha1234"})
    resp = client.post("/auth/login", json={"email": email, "password": "senha1234"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@requires_db
def test_cannot_report_same_question_twice(client):
    author_headers = _register_and_login(client, "Autor", "autor3@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O ceu e azul durante o dia.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador", "reportador@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason": "resposta incorreta", "reason_category": "Resposta incorreta"},
        headers=reporter_headers,
    )
    assert resp.status_code == 201

    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason": "de novo", "reason_category": "Outro"},
        headers=reporter_headers,
    )
    assert resp.status_code == 409


@requires_db
def test_invalid_reason_category_is_rejected(client):
    author_headers = _register_and_login(client, "Autor4", "autor4@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "A agua ferve a 100 graus ao nivel do mar.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador2", "reportador2@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason": "motivo qualquer", "reason_category": "categoria-que-nao-existe"},
        headers=reporter_headers,
    )
    assert resp.status_code == 422


@requires_db
def test_accepting_report_credits_reporter_reputation(client):
    admin_headers = _register_and_login(client, "Prof3", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor5", "autor5@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O Brasil fica na America do Sul.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador3", "reportador3@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason": "duplicada", "reason_category": "Pergunta duplicada"},
        headers=reporter_headers,
    )
    report_id = resp.json()["id"]
    assert resp.json()["status"] == "pending"

    resp = client.get("/stats/me", headers=reporter_headers)
    assert resp.json()["accepted_reports_count"] == 0

    resp = client.put(f"/admin/reports/{report_id}/accept", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    resp = client.get("/stats/me", headers=reporter_headers)
    assert resp.json()["accepted_reports_count"] == 1
    assert resp.json()["rejected_reports_count"] == 0

    # aceitar/rejeitar o reporte e' independente de aprovar/remover a pergunta
    resp = client.get("/stats/me", headers=author_headers)
    assert resp.json()["questions_removed_count"] == 0


@requires_db
def test_rejecting_report_credits_reporter_rejected_count(client):
    admin_headers = _register_and_login(client, "Prof4", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor6", "autor6@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "Marte e o quarto planeta do sistema solar.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador4", "reportador4@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason": "nao concordo", "reason_category": "Outro"},
        headers=reporter_headers,
    )
    report_id = resp.json()["id"]

    resp = client.put(f"/admin/reports/{report_id}/reject", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    resp = client.get("/stats/me", headers=reporter_headers)
    assert resp.json()["rejected_reports_count"] == 1
    assert resp.json()["accepted_reports_count"] == 0


@requires_db
def test_removed_question_credits_author_penalty_independent_of_reports(client):
    admin_headers = _register_and_login(client, "Prof5", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor7", "autor7@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O oceano Pacifico e o maior oceano do planeta.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]
    author_me = client.get("/auth/me", headers=author_headers).json()

    reporter_headers = _register_and_login(client, "Reportador5", "reportador5@example.com")
    client.post(
        f"/questions/{question_id}/report",
        json={"reason": "motivo", "reason_category": "Fora do tema"},
        headers=reporter_headers,
    )

    resp = client.put(f"/admin/questions/{question_id}/remove", headers=admin_headers)
    assert resp.status_code == 200

    resp = client.get("/stats/me", headers=author_headers)
    assert resp.json()["questions_removed_count"] == 1

    resp = client.get("/admin/users", headers=admin_headers)
    users_by_email = {u["email"]: u for u in resp.json()}
    assert users_by_email["autor7@example.com"]["questions_removed_count"] == 1
    assert users_by_email["autor7@example.com"]["id"] == author_me["id"]

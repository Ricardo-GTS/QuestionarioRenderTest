from tests.conftest import requires_db

ADMIN_EMAIL = "admin@example.com"  # precisa bater com o default de ADMIN_EMAILS em conftest.py


@requires_db
def test_non_admin_gets_403_on_admin_routes(client):
    client.post(
        "/auth/register", json={"name": "Aluno", "email": "aluno2@example.com", "password": "senha1234"}
    )
    resp = client.post("/auth/login", json={"email": "aluno2@example.com", "password": "senha1234"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/admin/questions", headers=headers).status_code == 403
    assert client.get("/admin/users", headers=headers).status_code == 403
    assert client.get("/admin/stats", headers=headers).status_code == 403
    assert client.get("/admin/settings", headers=headers).status_code == 403


@requires_db
def test_admin_can_moderate_manage_and_configure(client, db_session):
    from app.core.security import hash_password
    from app.models.enums import QuestionStatus
    from app.models.question import Question
    from app.models.report import Report
    from app.models.user import User

    client.post("/auth/register", json={"name": "Prof", "email": ADMIN_EMAIL, "password": "senha1234"})
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "senha1234"})
    admin_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.get("/auth/me", headers=admin_headers)
    assert resp.json()["is_admin"] is True

    resp = client.get("/admin/settings", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["quiz_size"] == 10

    resp = client.put("/admin/settings", json={"quiz_size": 3}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["quiz_size"] == 3

    resp = client.put("/admin/settings", json={"similarity_threshold": 2}, headers=admin_headers)
    assert resp.status_code == 422

    author = User(name="Autor", email="autor2@example.com", hashed_password=hash_password("senha1234"))
    db_session.add(author)
    db_session.commit()

    question = Question(
        author_id=author.id,
        statement="Pergunta reportada de teste",
        correct_answer=True,
        embedding=[0.0] * 768,
        status=QuestionStatus.REPORTED,
    )
    db_session.add(question)
    db_session.commit()

    db_session.add(
        Report(question_id=question.id, reporter_id=author.id, reason="motivo teste", reason_category="Outro")
    )
    db_session.commit()
    question_id = question.id

    resp = client.get("/admin/questions?status=reported", headers=admin_headers)
    assert resp.status_code == 200
    assert any(q["id"] == question_id and q["report_count"] == 1 for q in resp.json())

    resp = client.put(f"/admin/questions/{question_id}/approve", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    resp = client.get("/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    users_by_email = {u["email"]: u for u in resp.json()}
    assert ADMIN_EMAIL in users_by_email
    assert "autor2@example.com" in users_by_email

    resp = client.delete(f"/admin/users/{users_by_email['autor2@example.com']['id']}", headers=admin_headers)
    assert resp.status_code == 204

    resp = client.get("/admin/stats", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["total_users"] >= 1


@requires_db
def test_admin_cannot_delete_own_account_via_admin_route(client):
    client.post("/auth/register", json={"name": "Prof2", "email": ADMIN_EMAIL, "password": "senha1234"})
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "senha1234"})
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    me = client.get("/auth/me", headers=headers).json()
    resp = client.delete(f"/admin/users/{me['id']}", headers=headers)
    assert resp.status_code == 400

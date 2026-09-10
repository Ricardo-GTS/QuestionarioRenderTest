from tests.conftest import requires_db


@requires_db
def test_register_login_and_duplicate_question_is_discarded(client):
    resp = client.post(
        "/auth/register",
        json={"name": "Aluno", "email": "aluno@example.com", "password": "senha1234"},
    )
    assert resp.status_code == 201

    resp = client.post("/auth/login", json={"email": "aluno@example.com", "password": "senha1234"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/questions",
        json={"statement": "O Sol e uma estrela.", "correct_answer": True, "category": "ciencias"},
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.post(
        "/questions",
        json={"statement": "O Sol e uma estrela.", "correct_answer": True},
        headers=headers,
    )
    assert resp.status_code == 409
    assert "similar_questions" in resp.json()["detail"]


@requires_db
def test_report_flags_question_after_threshold(client, db_session):
    from app.core.config import settings
    from app.core.security import hash_password
    from app.models.enums import QuestionStatus
    from app.models.question import Question
    from app.models.user import User

    author = User(name="Autor", email="autor@example.com", hashed_password=hash_password("senha1234"))
    db_session.add(author)
    db_session.commit()

    question = Question(
        author_id=author.id,
        statement="Pergunta a ser reportada",
        correct_answer=True,
        embedding=[0.0] * 768,
    )
    db_session.add(question)
    db_session.commit()
    question_id = question.id

    resp = client.post(
        "/auth/register", json={"name": "Rep", "email": "rep@example.com", "password": "senha1234"}
    )
    assert resp.status_code == 201
    resp = client.post("/auth/login", json={"email": "rep@example.com", "password": "senha1234"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(settings.report_threshold):
        resp = client.post(
            f"/questions/{question_id}/report",
            json={"reason": "resposta incorreta"},
            headers=headers,
        )
        assert resp.status_code == 201

    db_session.refresh(question)
    assert question.status == QuestionStatus.REPORTED

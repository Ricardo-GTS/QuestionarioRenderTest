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
def test_reason_category_is_required(client):
    author_headers = _register_and_login(client, "Autor4b", "autor4b@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O sol nasce no leste.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador2b", "reportador2b@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason": "motivo qualquer"},
        headers=reporter_headers,
    )
    assert resp.status_code == 422


@requires_db
def test_reason_is_optional_when_category_is_not_outro(client):
    # O embedding fake do conftest faz duas perguntas quaisquer parecerem
    # 100% similares entre si -- cada teste aqui usa so' 1 pergunta pra nao
    # esbarrar no dedupe semantico (RF02), que nao tem relacao com esse teste.
    author_headers = _register_and_login(client, "Autor4c", "autor4c@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O gelo e mais denso que a agua liquida.", "correct_answer": False},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador2c", "reportador2c@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason_category": "Resposta incorreta"},
        headers=reporter_headers,
    )
    assert resp.status_code == 201


@requires_db
def test_reason_required_when_category_is_outro(client):
    author_headers = _register_and_login(client, "Autor4d", "autor4d@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "A velocidade da luz e constante no vacuo.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador2d", "reportador2d@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason_category": "Outro"},
        headers=reporter_headers,
    )
    assert resp.status_code == 422

    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason_category": "Outro", "reason": "motivo especifico"},
        headers=reporter_headers,
    )
    assert resp.status_code == 201


@requires_db
def test_pending_reports_queue_shows_question_regardless_of_status(client):
    admin_headers = _register_and_login(client, "Prof3", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor5", "autor5@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O Brasil fica na America do Sul.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    # 1 reporte so' -- abaixo do limiar de auto-flag, mas ja deve aparecer na fila.
    reporter_headers = _register_and_login(client, "Reportador3", "reportador3@example.com")
    resp = client.post(
        f"/questions/{question_id}/report",
        json={"reason": "duplicada", "reason_category": "Pergunta duplicada"},
        headers=reporter_headers,
    )
    reporter_name = "Reportador3"

    resp = client.get("/admin/questions/pending-reports", headers=admin_headers)
    assert resp.status_code == 200
    queue = resp.json()
    entry = next(q for q in queue if q["id"] == question_id)
    assert entry["status"] == "active"  # ainda nao atingiu o limiar de auto-flag
    assert entry["correct_answer"] is True
    assert entry["reports"][0]["reporter_name"] == reporter_name
    assert entry["reports"][0]["reason"] == "duplicada"


@requires_db
def test_approve_removal_credits_reporters_and_removes_question(client):
    admin_headers = _register_and_login(client, "Prof4", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor6", "autor6@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "Marte e o quarto planeta do sistema solar.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]
    author_id = client.get("/auth/me", headers=author_headers).json()["id"]

    reporter_headers = _register_and_login(client, "Reportador4", "reportador4@example.com")
    client.post(
        f"/questions/{question_id}/report",
        json={"reason": "nao concordo", "reason_category": "Outro"},
        headers=reporter_headers,
    )

    resp = client.put(f"/admin/questions/{question_id}/approve-removal", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "removed"

    resp = client.get("/stats/me", headers=reporter_headers)
    assert resp.json()["accepted_reports_count"] == 1

    resp = client.get("/stats/me", headers=author_headers)
    assert resp.json()["questions_removed_count"] == 1

    resp = client.get("/admin/users", headers=admin_headers)
    users_by_email = {u["email"]: u for u in resp.json()}
    assert users_by_email["autor6@example.com"]["questions_removed_count"] == 1
    assert users_by_email["autor6@example.com"]["id"] == author_id

    # resolvida -- some da fila de pendentes
    resp = client.get("/admin/questions/pending-reports", headers=admin_headers)
    assert all(q["id"] != question_id for q in resp.json())


@requires_db
def test_reject_removal_credits_rejected_and_keeps_question_active(client):
    admin_headers = _register_and_login(client, "Prof5", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor7", "autor7@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O oceano Pacifico e o maior oceano do planeta.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador5", "reportador5@example.com")
    client.post(
        f"/questions/{question_id}/report",
        json={"reason": "motivo", "reason_category": "Fora do tema"},
        headers=reporter_headers,
    )

    resp = client.put(f"/admin/questions/{question_id}/reject-removal", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    resp = client.get("/stats/me", headers=reporter_headers)
    assert resp.json()["rejected_reports_count"] == 1
    assert resp.json()["accepted_reports_count"] == 0

    resp = client.get("/stats/me", headers=author_headers)
    assert resp.json()["questions_removed_count"] == 0

    resp = client.get("/admin/questions/pending-reports", headers=admin_headers)
    assert all(q["id"] != question_id for q in resp.json())


@requires_db
def test_approve_removal_resolves_multiple_reporters_at_once(client):
    admin_headers = _register_and_login(client, "Prof6", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor8", "autor8@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "A lua e um satelite natural da Terra.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter1 = _register_and_login(client, "Reportador6", "reportador6@example.com")
    reporter2 = _register_and_login(client, "Reportador7", "reportador7@example.com")
    client.post(
        f"/questions/{question_id}/report",
        json={"reason": "motivo 1", "reason_category": "Outro"},
        headers=reporter1,
    )
    client.post(
        f"/questions/{question_id}/report",
        json={"reason": "motivo 2", "reason_category": "Outro"},
        headers=reporter2,
    )

    resp = client.get("/admin/questions/pending-reports", headers=admin_headers)
    entry = next(q for q in resp.json() if q["id"] == question_id)
    assert len(entry["reports"]) == 2

    client.put(f"/admin/questions/{question_id}/approve-removal", headers=admin_headers)

    assert client.get("/stats/me", headers=reporter1).json()["accepted_reports_count"] == 1
    assert client.get("/stats/me", headers=reporter2).json()["accepted_reports_count"] == 1


@requires_db
def test_reactivating_removed_question_via_approve(client):
    admin_headers = _register_and_login(client, "Prof7", ADMIN_EMAIL)
    author_headers = _register_and_login(client, "Autor9", "autor9@example.com")
    resp = client.post(
        "/questions",
        json={"statement": "O corpo humano tem 206 ossos.", "correct_answer": True},
        headers=author_headers,
    )
    question_id = resp.json()["id"]

    reporter_headers = _register_and_login(client, "Reportador8", "reportador8@example.com")
    client.post(
        f"/questions/{question_id}/report",
        json={"reason": "motivo", "reason_category": "Outro"},
        headers=reporter_headers,
    )
    client.put(f"/admin/questions/{question_id}/approve-removal", headers=admin_headers)

    resp = client.get("/admin/questions?status=removed", headers=admin_headers)
    assert any(q["id"] == question_id for q in resp.json())

    resp = client.put(f"/admin/questions/{question_id}/approve", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

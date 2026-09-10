import os

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


class ApiError(Exception):
    def __init__(self, status_code: int, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


def _auth_headers(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


async def _request(method: str, path: str, token: str | None = None, **kwargs) -> dict:
    url = f"{API_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, headers=_auth_headers(token), **kwargs)

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = response.text
        raise ApiError(response.status_code, detail)

    if response.status_code == 204:
        return {}
    return response.json()


async def register(name: str, email: str, password: str) -> dict:
    return await _request("POST", "/auth/register", json={"name": name, "email": email, "password": password})


async def login(email: str, password: str) -> dict:
    return await _request("POST", "/auth/login", json={"email": email, "password": password})


async def get_me(token: str) -> dict:
    return await _request("GET", "/auth/me", token=token)


async def update_me(token: str, **fields) -> dict:
    payload = {k: v for k, v in fields.items() if v is not None}
    return await _request("PUT", "/auth/me", token=token, json=payload)


async def delete_me(token: str) -> dict:
    return await _request("DELETE", "/auth/me", token=token)


async def create_question(token: str, statement: str, correct_answer: bool, category: str | None) -> dict:
    return await _request(
        "POST",
        "/questions",
        token=token,
        json={"statement": statement, "correct_answer": correct_answer, "category": category},
    )


async def get_quiz(token: str) -> dict:
    return await _request("GET", "/quiz", token=token)


async def submit_quiz(token: str, answers: list[dict]) -> dict:
    return await _request("POST", "/quiz/submit", token=token, json={"answers": answers})


async def report_question(token: str, question_id: int, reason: str, reason_category: str | None) -> dict:
    return await _request(
        "POST",
        f"/questions/{question_id}/report",
        token=token,
        json={"reason": reason, "reason_category": reason_category},
    )

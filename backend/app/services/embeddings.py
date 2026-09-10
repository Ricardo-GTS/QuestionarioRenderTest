import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingServiceError(Exception):
    pass


async def get_embedding(text: str) -> list[float]:
    url = f"{settings.ollama_host}/api/embeddings"
    payload = {"model": settings.ollama_embed_model, "prompt": text}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Falha ao gerar embedding via Ollama: %s", exc)
        raise EmbeddingServiceError("Nao foi possivel gerar o embedding da pergunta") from exc

    data = response.json()
    embedding = data.get("embedding")
    if not embedding:
        logger.error("Resposta do Ollama sem campo 'embedding': %s", data)
        raise EmbeddingServiceError("Resposta invalida do servico de embeddings")

    return embedding

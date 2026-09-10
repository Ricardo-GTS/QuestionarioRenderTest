# Questionario

Sistema web de apoio a educacao onde alunos criam e respondem perguntas de Verdadeiro/Falso, com deduplicacao semantica via embeddings (Ollama + pgvector) e moderacao automatica por reportes.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL (extensao `pgvector`)
- **Frontend:** Reflex (Python, compila para SPA React)
- **Embeddings:** Ollama rodando localmente, modelo `nomic-embed-text`
- **Autenticacao:** JWT em header `Authorization: Bearer <token>` (guardado no state/localStorage do Reflex)

## Rodando com Docker (recomendado)

```bash
cp .env.example .env   # ajuste os valores se necessario
docker compose up --build
```

Isso sobe: Postgres com pgvector, Ollama (baixando o modelo `nomic-embed-text` automaticamente via o servico `ollama-init`), o backend FastAPI e o frontend Reflex.

- Frontend: http://localhost:3000
- Backend (Swagger): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/health

## Variaveis de ambiente

Ver `.env.example`. Nenhum valor de negocio (limiar de similaridade, tamanho do questionario, limiar de reportes) e hardcoded — tudo vem de env vars:

| Variavel | Descricao | Default |
|---|---|---|
| `DATABASE_URL` | URL de conexao do Postgres (SQLAlchemy) | - |
| `OLLAMA_HOST` | URL do servidor Ollama | `http://ollama:11434` |
| `OLLAMA_EMBED_MODEL` | Modelo de embedding usado | `nomic-embed-text` |
| `SIMILARITY_THRESHOLD` | Limiar de similaridade de cosseno para descartar pergunta duplicada | `0.75` |
| `QUIZ_SIZE` | Quantidade de perguntas por questionario | `10` |
| `REPORT_THRESHOLD` | Quantidade de reportes para flagar uma pergunta | `3` |
| `JWT_SECRET` | Segredo usado para assinar o JWT | - |
| `JWT_EXPIRE_MINUTES` | Validade do token em minutos | `60` |

## Desenvolvimento local (sem Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://questionario:questionario@localhost:5432/questionario
export JWT_SECRET=dev-secret
alembic upgrade head
uvicorn app.main:app --reload
```

### Testes do backend

```bash
cd backend
pytest                     # roda tudo; testes de integracao fazem skip se nao houver Postgres+pgvector disponivel
pytest tests/test_similarity.py -v   # rodar um arquivo/teste especifico
```

As variaveis `DATABASE_URL`/`JWT_SECRET` para os testes tem default em `tests/conftest.py` (usa `TEST_DATABASE_URL` se definida, ou `postgresql+psycopg://questionario:questionario@localhost:5432/questionario_test`).

### Migrations

```bash
cd backend
alembic revision -m "descricao"   # nova migration
alembic upgrade head              # aplicar
alembic downgrade -1              # reverter a ultima
```

### Frontend

```bash
cd frontend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export API_BASE_URL=http://localhost:8000
reflex run
```

## Fluxo critico (dedupe semantica)

Ao criar uma pergunta (`POST /questions`): o backend gera o embedding do enunciado via Ollama, busca as perguntas ativas mais proximas por similaridade de cosseno no pgvector (indice HNSW) e, se a similaridade for `>= SIMILARITY_THRESHOLD`, descarta a pergunta e retorna 409 com a(s) pergunta(s) similar(es); caso contrario, persiste a pergunta com seu embedding.

## Moderacao

Cada reporte em uma pergunta (`POST /questions/{id}/report`) e contabilizado; ao atingir `REPORT_THRESHOLD` reportes, a pergunta muda de status para `reported` e sai do pool de perguntas ativas usadas nos questionarios (sem remocao automatica definitiva).

## Fora do escopo do MVP

- Recuperacao de senha (fluxo por e-mail) — fase 2
- Gamificacao (ranking, pontos, badges)
- Perguntas em formatos alem de V/F
- Painel de moderacao humana (a moderacao do MVP e so a flag automatica por reportes)

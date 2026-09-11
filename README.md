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
| `DB_POOL_SIZE` | Conexoes persistentes no pool do Postgres | `20` |
| `DB_MAX_OVERFLOW` | Conexoes extras permitidas em picos, alem do pool | `20` |
| `OLLAMA_HOST` | URL do servidor Ollama | `http://ollama:11434` |
| `OLLAMA_EMBED_MODEL` | Modelo de embedding usado | `nomic-embed-text` |
| `SIMILARITY_THRESHOLD` | Limiar de similaridade de cosseno para descartar pergunta duplicada | `0.75` |
| `QUIZ_SIZE` | Quantidade de perguntas por questionario | `10` |
| `REPORT_THRESHOLD` | Quantidade de reportes para flagar uma pergunta | `3` |
| `JWT_SECRET` | Segredo usado para assinar o JWT | - |
| `JWT_EXPIRE_MINUTES` | Validade do token em minutos | `10080` (7 dias) |
| `ADMIN_EMAILS` | E-mails (separados por virgula) com acesso ao painel de admin | vazio |

`SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` no `.env` sao so o valor **inicial** (semeado na migration `0002`) — depois do primeiro boot, esses 3 ficam editaveis em runtime pelo painel de admin (`/admin/settings`), sem precisar reiniciar o container.

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

## Concorrencia e rate limiting

- **Pool de conexoes do Postgres:** configurado via `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` (default 20+20 = ate 40 conexoes simultaneas), acima do default do SQLAlchemy (5+10) para aguentar varios alunos usando ao mesmo tempo.
- **Rate limiting:** `POST /auth/login` (5/minuto por IP) e `POST /questions` (20/minuto por IP), via `slowapi`. Excede o limite -> `429 Too Many Requests`. Configuravel em `backend/app/core/rate_limit.py`.
- Gargalo esperado sob carga: geracao de embedding no Ollama e' a operacao mais pesada (CPU-bound, sem GPU) — perguntas criadas em rajada ficam mais lentas para salvar, mas nao travam o sistema.

## Painel de admin (professor)

Quem estiver listado em `ADMIN_EMAILS` vira admin automaticamente ao logar (sem cadastro especial, sem coluna de role no banco). Acesso em `/admin`:

- **Dashboard** (`/admin`) — totais de usuarios/perguntas/reportes, taxa media de acerto, perguntas e reportes por categoria.
- **Moderacao** (`/admin/moderation`) — lista perguntas reportadas, aprova (volta pra `active`), remove (`removed`) ou edita o enunciado/resposta/categoria (recalcula o embedding se o enunciado mudar).
- **Usuarios** (`/admin/users`) — lista com contagem de perguntas por usuario, exclusao de conta (com confirmacao; nao permite excluir a propria conta admin por ali).
- **Configuracoes** (`/admin/settings`) — edita `SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` em runtime.

## Fora do escopo do MVP

- Recuperacao de senha (fluxo por e-mail) — fase 2
- Gamificacao (ranking, pontos, badges)
- Perguntas em formatos alem de V/F
- Tabela de auditoria dedicada para acoes do admin (hoje fica so no log estruturado)

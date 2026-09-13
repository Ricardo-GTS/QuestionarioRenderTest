# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack confirmada

| Camada | Escolha |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 + Alembic |
| Frontend | Reflex (Python, compila para SPA React) |
| Banco | PostgreSQL + extensao `pgvector` (indice HNSW, distancia de cosseno) |
| Embeddings | Ollama local, modelo `nomic-embed-text` |
| Autenticacao | JWT em header `Authorization: Bearer` (guardado no state/localStorage do Reflex, nao em cookie httpOnly). Login com Google via `reflex-google-auth` e' opcional/aditivo, ver secao "Login com Google" abaixo |
| Moderacao | Flag automatica apos `REPORT_THRESHOLD` reportes (default 3) — sem remocao automatica |
| Painel de admin | Quem estiver em `ADMIN_EMAILS` (.env) vira admin no login — sem coluna `role`, sem auto-promocao |
| Recuperacao de senha | Fora do MVP (fase 2) |

Essas decisoes vieram de uma entrevista de esclarecimento explicita com o usuario — nao as reabra sem confirmar de novo. Detalhes de cada trade-off estao no historico da conversa; o resumo pratico:
- Reflex foi escolhido sobre Django porque o nucleo tecnico do projeto (embedding assincrono + pgvector) pesa mais que o auth/admin gratis do Django, que o MVP nao usaria mesmo (moderacao e automatica, nao tem painel humano).
- JWT em header (nao cookie httpOnly) foi escolhido por simplicidade, aceitando o risco de XSS por ser um sistema educacional sem dados sensiveis — evita lidar com CORS/SameSite entre o servidor Reflex e o FastAPI.

## Comandos

```bash
# Subir tudo (Postgres+pgvector, Ollama, backend, frontend)
cp .env.example .env
docker compose up --build

# Backend local
cd backend && pip install -r requirements.txt
alembic upgrade head              # aplicar migrations
alembic revision -m "descricao"   # nova migration
uvicorn app.main:app --reload
pytest                            # todos os testes (integracao faz skip sem Postgres+pgvector)
pytest tests/test_similarity.py -v -k nome_do_teste   # um teste especifico

# Frontend local
cd frontend && pip install -r requirements.txt
reflex run
```

Variaveis de ambiente completas em `.env.example` — `SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` nunca devem ser hardcoded no codigo.

## Arquitetura

```
backend/app/
├── main.py              # monta o FastAPI app e inclui os routers
├── core/                # config (pydantic-settings, admin_emails), security (hash + JWT + is_admin_email), logging
├── db/                  # engine/session, Base declarativa
├── models/               # User (hashed_password opcional + google_sub p/ login Google), Question (coluna Vector(768)), Report (status pending/accepted/rejected + unique question_id+reporter_id), AppSettings (linha unica), QuizAttempt
├── schemas/              # Pydantic request/response (user, question, quiz, report, admin)
├── api/routers/          # auth, questions, quiz, reports, stats (reputacao do proprio usuario), health, admin
├── api/deps.py           # get_db, get_current_user, get_current_admin (403 se email fora de ADMIN_EMAILS)
└── services/
    ├── embeddings.py      # chama Ollama /api/embeddings (async)
    ├── similarity.py      # busca HNSW por cosseno + filtro por threshold (logica pura testavel em filter_by_threshold)
    ├── quiz.py             # selecao aleatoria + calculo de pontuacao + record_attempt (persiste QuizAttempt)
    ├── moderation.py       # reportes + regra de flag (should_flag) + approve/remove/update_question + accept_report/reject_report (veredito individual do admin sobre um reporte)
    ├── runtime_settings.py # SIMILARITY_THRESHOLD/QUIZ_SIZE/REPORT_THRESHOLD efetivos (tabela app_settings, editavel via /admin/settings)
    └── stats.py            # agregacoes do dashboard (compute_average_score_percent e' a parte pura/testavel) + compute_user_reputation/compute_all_users_reputation (reportes aceitos/rejeitados e perguntas removidas, por usuario -- calculado na hora, sem contador denormalizado)

frontend/questionario/
├── api_client.py          # wrapper httpx, injeta Authorization no header (inclui admin_* )
├── state/                 # AuthState (+is_admin), QuestionState, QuizState, ReportState (+ REASON_CATEGORIES fixo), StatsState, admin_state.py (4 states, AdminModerationState com reports achatado -- ver armadilha do rx.foreach abaixo)
├── pages/                 # login, register, home, quiz, account, estatisticas (reputacao do proprio usuario), admin_dashboard/moderation/users/settings
└── components/            # navbar (link Admin condicional), admin_nav, report_modal, question_card
```

**Fluxo critico (RF02/RF05 — dedupe semantica):** `POST /questions` chama `services/embeddings.get_embedding` (Ollama, async) → `services/similarity.find_similar_active_questions` busca vizinhos via `Question.embedding.cosine_distance(...)` (indice HNSW, `vector_cosine_ops`) → se similaridade `>= SIMILARITY_THRESHOLD`, retorna 409 com as perguntas similares em vez de salvar.

**Moderacao (RF04):** `POST /questions/{id}/report` grava o `Report` (um por par question_id+reporter_id -- unique constraint, 409 se repetir) e `services/moderation.register_report` verifica a contagem; ao atingir `REPORT_THRESHOLD`, muda `Question.status` para `reported` (sai do pool usado em `services/quiz.pick_random_questions`, que so seleciona `status == active`). Cada `Report` individual tem seu proprio veredito (`status`: pending/accepted/rejected), decidido pelo admin via `PUT /admin/reports/{id}/accept|reject` -- **independente** de Aprovar/Remover a pergunta (acoes separadas, sem automatismo entre uma e outra). Aceitar/rejeitar um reporte alimenta a reputacao de quem reportou; remover a pergunta alimenta a penalidade de quem a criou -- ambas calculadas na hora (`services/stats.compute_user_reputation`), expostas em `GET /stats/me` (pagina "Estatisticas" do aluno) e em `GET /admin/users` (visao do admin).

**Padrao dos services:** a logica de decisao (threshold de similaridade, regra de flag, calculo de pontuacao, media do dashboard) fica em funcoes puras sem dependencia de DB (`filter_by_threshold`, `should_flag`, `score_quiz`, `compute_average_score_percent`) justamente para serem testadas sem precisar de Postgres — ver `backend/tests/`. Ao adicionar regra de negocio nova, prefira esse padrao em vez de misturar decisao com a query SQL.

**Admin (painel do professor):** quem esta em `ADMIN_EMAILS` (.env, lista separada por virgula) vira admin — nao ha coluna `role` nem fluxo de auto-promocao. `GET /auth/me` retorna `is_admin` computado (nunca expõe a lista de e-mails pro frontend). Todas as rotas `/admin/*` exigem `get_current_admin`. `SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` no `.env` sao so o default inicial (seed da migration `0002`) — o valor efetivo mora na tabela `app_settings` (linha unica, id=1) e e' editavel via `PUT /admin/settings`; `services/similarity.py`, `quiz.py` e `moderation.py` leem de la (`get_effective_settings(db)`), nunca do `settings` estatico direto pra esses 3 campos.

**Login com Google (opcional, aditivo):** `POST /auth/google` recebe o id_token do Google (`credential`), verifica assinatura/audience/expiracao via `google-auth` (`core/security.verify_google_id_token`, audience = `GOOGLE_CLIENT_ID`) e emite o mesmo JWT que `/auth/login` -- nao ha sessao/estado paralelo. Resolve o usuario por `google_sub` e, se nao achar, por `email` (linka a conta existente em vez de duplicar); so cria usuario novo se nenhum dos dois bater. `User.hashed_password` e' `nullable` por causa disso (conta so-Google nao tem senha) -- `login()` (email/senha) trata `hashed_password is None` como credencial invalida em vez de estourar no bcrypt. No frontend, `reflex_google_auth.google_login`/`google_oauth_provider` (pacote `reflex-google-auth`, so' os componentes visuais) sao usados com `on_success=AuthState.handle_google_login` custom -- nao usamos o `GoogleAuthState` nem a verificacao embutida do pacote, propositalmente, pra manter um unico dono da sessao (nosso JWT/`AuthState.token`). Sem `GOOGLE_CLIENT_ID` configurado, o botao aparece mas o backend rejeita qualquer token (feature desligada, resto do app intacto).

**Reflex — armadilha conhecida:** esta versao do Reflex (`0.9.10.post2`) **nao gera setters automaticos** (`set_<campo>`) para vars de state simples — cada campo de formulario precisa de um metodo `set_<campo>` explicito na classe de State (ver `AuthState`, `QuestionState`, `ReportState`). Tambem, `rx.foreach` nao funciona sobre uma var `dict`/`Any` (ex: indexar um dict generico) — precisa de uma var `list[...]` com tipo concreto (ver `QuizState.feedback` como separado de um `result: dict` generico; e `AdminModerationState.reports`, uma lista achatada separada de `questions`, porque `question["reports"]` -- indexar dentro de um item de `questions: list[dict]` -- nao e' uma var list[...] concreta). Tambem, `rx.theme(..., color_mode=...)` (forcar aparencia clara/escura so' num sub-componente) **nao funciona** nesta versao -- o prop de aparencia e' silenciosamente descartado na compilacao (confirmado inspecionando o JSX gerado: o `<Theme>` compilado nunca recebe `appearance`, so' `css`). Pra forcar aparencia num sub-componente, aplique a classe do Radix direto via `class_name="radix-themes light light-theme"` (ou `dark`/`dark-theme`) no componente raiz do sub-componente -- e' assim que o Radix decide as variaveis de cor (`--gray-12` etc.), ver `components/report_modal.py`.

**Backend — pins de versao testados contra Python 3.13/3.14:** os pins em `backend/requirements.txt` foram ajustados apos erros reais de instalacao/execucao em Python mais novo que 3.12 (o que a imagem `python:3.12-slim` do Dockerfile usa, mas o dev pode ter localmente): `sqlalchemy==2.0.35` original quebrava a resolucao de `Mapped[str | None]` (corrigido para `2.0.52`), `psycopg[binary]==3.2.2` nao tinha wheel (corrigido para `3.2.10`), `pydantic==2.9.2` falhava ao compilar `pydantic-core` do zero (corrigido para `2.13.5`). Tambem trocamos `passlib[bcrypt]` pelo pacote `bcrypt` direto em `core/security.py` — `passlib` esta sem manutencao e quebra com versoes recentes de `bcrypt` (`ValueError: password cannot be longer than 72 bytes` mesmo em senhas curtas). Se reintroduzir uma lib desse tipo, valide a instalacao antes de assumir que o pin funciona.

## Testes

`backend/tests/` tem duas categorias:
- **Unitarios** (`test_similarity.py`, `test_moderation.py`, `test_quiz_service.py`, `test_admin_auth.py`, `test_runtime_settings.py`, `test_stats.py`): puros, rodam em qualquer lugar, sem DB.
- **Integracao** (`test_api_flow.py`, `test_admin_flow.py`, `test_google_auth.py`, `test_report_reputation.py`): sobem o `TestClient` do FastAPI contra um Postgres real com pgvector; fazem `skip` automatico (via `requires_db` em `conftest.py`) se `DATABASE_URL`/`TEST_DATABASE_URL` nao estiver acessivel. O client de teste sobrescreve `get_embedding` por um embedding deterministico para nao depender do Ollama. `test_google_auth.py` monkeypatcha `verify_google_id_token` (via `monkeypatch.setattr` no modulo do router) pra nao depender da API real do Google -- mesma tecnica. `conftest.py` seta `ADMIN_EMAILS=admin@example.com` por default — os testes de admin registram/logam com esse e-mail pra virar admin. `conftest.py` tambem desliga o rate limiter (`limiter.enabled = False`) — sem isso, os varios logins entre arquivos de teste diferentes dividiriam o mesmo limite de 5/min (TestClient sempre usa o mesmo IP fake) e quebrariam testes sem relacao nenhuma com rate limiting.

## Especificacao de requisitos (referencia)

Requisitos funcionais e nao funcionais originais do projeto — uteis para checar se uma mudanca ainda atende ao escopo do MVP.

### Visao geral do produto

Plataforma web onde alunos se cadastram, criam perguntas de Verdadeiro ou Falso sobre qualquer conteúdo de estudo, e respondem questionários montados aleatoriamente a partir do banco de perguntas de todos os usuários. O sistema evita duplicação semântica de perguntas usando embeddings + busca vetorial.

### Requisitos Funcionais (RF)

**RF01 — Cadastro e autenticação**
- Aluno se cadastra com nome, e-mail e senha.
- Login com e-mail/senha (JWT em header `Authorization`).
- Login alternativo com Google (`POST /auth/google`, opcional/aditivo, adicionado após o MVP) -- cria ou vincula a conta pelo e-mail, sem exigir senha.
- Aluno pode editar seus dados de conta (nome, senha, e-mail) e excluir a própria conta.
- Recuperação de senha: fora do MVP (fase 2).

**RF02 — Criação de perguntas V/F**
- Usuário autenticado cria uma pergunta: enunciado (texto), resposta correta (Verdadeiro/Falso), categoria/tema opcional.
- Antes de salvar, o sistema calcula o embedding do enunciado e busca no banco vetorial perguntas existentes com **similaridade ≥ 75%** (configurável).
  - Se encontrar, a pergunta é **descartada** (não salva) e o sistema exibe ao usuário a(s) pergunta(s) já existente(s) mais similar(es).
  - Se não encontrar, a pergunta é salva normalmente, com seu embedding persistido junto.
- Cada pergunta guarda: autor, enunciado, resposta correta, embedding, categoria, data de criação, status (ativa/reportada/removida).

**RF03 — Questionário aleatório**
- Usuário solicita um questionário; o sistema seleciona X perguntas aleatórias (configurável, default 10) dentre as perguntas ativas de outros usuários (exclui as do próprio usuário).
- Usuário responde V ou F para cada pergunta.
- Ao final, sistema mostra pontuação (acertos/total) e feedback por pergunta.

**RF04 — Reporte de perguntas**
- Usuário pode reportar uma pergunta como incorreta/problemática, com motivo (texto livre) + tipo de problema (lista fechada: resposta incorreta, enunciado ambíguo ou confuso, conteúdo ofensivo ou inadequado, pergunta duplicada, fora do tema, outro).
- Um usuário só pode reportar a mesma pergunta uma vez.
- Reportes ficam associados à pergunta e ao usuário que reportou, com data.
- Regra de moderação: flag automática para revisão após N reportes (default configurável 3), sem remoção automática definitiva.
- Cada reporte individual é aceito ou rejeitado pelo admin (ação separada de aprovar/remover a pergunta). Reportes aceitos contam para a reputação de quem reportou; perguntas removidas contam como penalidade para quem as criou -- ambos visíveis para o usuário numa página "Estatísticas" e para o admin em Usuários (adicionado após o MVP).

**RF05 — Detecção de similaridade semântica (núcleo técnico)**
- Embedding do enunciado gerado localmente via Ollama (`nomic-embed-text`).
- Embeddings persistidos no Postgres via `pgvector`.
- Busca de vizinhos mais próximos por similaridade de cosseno, limiar de 75% configurável (env var, nunca hardcoded).

### Requisitos Não Funcionais (RNF)

- **Stack:** Backend FastAPI, Frontend Reflex, Postgres+pgvector, Ollama local (sem API paga externa).
- **Persistência:** SQLAlchemy + Alembic com migrations versionadas.
- **Segurança:** senhas com hash forte (bcrypt), validação de entrada em todos os endpoints (Pydantic). Rate limiting em `/auth/login` e `POST /questions` via `slowapi` (`core/rate_limit.py`, 5/min e 20/min por IP). Proteção CSRF/XSS ainda não implementada — considerar antes de produção.
- **Performance:** índice `hnsw` no pgvector para a busca vetorial; geração de embedding é assíncrona; pool de conexões do Postgres configurável (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`, default 20+20) para suportar vários alunos concorrentes.
- **Testes:** unitários para threshold de similaridade, seleção aleatória/scoring; integração para os principais endpoints.
- **Observabilidade:** logs estruturados nos pontos críticos (falha Ollama, pergunta descartada, reporte registrado); `/health` verificando Postgres e Ollama.
- **Containerização:** `docker-compose.yml` orquestra backend, frontend, Postgres+pgvector e Ollama; variáveis de ambiente via `.env`.
- **Usabilidade:** fluxo de quiz responsivo em mobile; mensagens de erro claras (ex: pergunta duplicada mostra a pergunta similar).

### Fora de escopo (MVP)

- Gamificação (ranking, pontos, badges).
- Perguntas em formatos além de V/F (múltipla escolha etc.).
- Recuperação de senha (fluxo de e-mail) — fase 2.
- Tabela de auditoria dedicada para ações do admin (hoje é só log estruturado, sem histórico consultável).

### Painel de admin (professor) — adicionado após o MVP

Requisito posterior ao MVP inicial: `role`-free (via `ADMIN_EMAILS`), moderação de perguntas reportadas (aprovar/remover/editar com recálculo de embedding), gestão de usuários (listar + excluir), dashboard (totais, taxa média de acerto via `QuizAttempt`, perguntas/reportes por categoria), e os 3 thresholds de negócio editáveis em runtime via `/admin/settings`. Ver seção "Arquitetura" acima para os arquivos.

Adicionado depois disso: login opcional com Google (ver seção "Login com Google" acima) e veredito individual por reporte (aceitar/rejeitar, alimentando a reputação do usuário -- ver seção "Moderação (RF04)" acima).

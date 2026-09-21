# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack confirmada

| Camada | Escolha |
|---|---|
| Backend + Frontend | Django (monolito), Templates server-side + HTMX para trocas parciais de tela |
| Banco | PostgreSQL + extensao `pgvector` (indice HNSW, distancia de cosseno), via `pgvector.django` |
| Embeddings | Ollama local, modelo `bge-m3` |
| Autenticacao | Sessao do Django (cookie `sessionid`, httpOnly). Login com Google e' opcional/aditivo, ver secao "Login com Google" abaixo |
| Moderacao | Flag automatica apos `REPORT_THRESHOLD` reportes (default 3) — sem remocao automatica |
| Painel de admin | Quem estiver em `ADMIN_EMAILS` (.env) vira admin no login — sem coluna `role`, sem auto-promocao (nao confundir com superuser do Django, ver secao "Django Admin nativo" abaixo) |
| Recuperacao de senha | Fora do MVP (fase 2) |

**Historico da decisao de stack** (relevante pra nao repetir a mesma discussao): o projeto comecou com FastAPI+SQLAlchemy+Alembic no backend e Reflex (Python compilando pra SPA React) no frontend — decisao tomada numa entrevista de esclarecimento explicita, resumida em duas razoes: (1) o nucleo tecnico do projeto (embedding assincrono + pgvector) pesava mais que o auth/admin gratis do Django, que o MVP inicial nao teria usado mesmo (moderacao era so automatica, sem painel humano); (2) JWT em header (nao cookie httpOnly) foi escolhido por simplicidade, aceitando risco de XSS por ser sistema educacional sem dados sensiveis, evitando lidar com CORS/SameSite entre Reflex e FastAPI. Essa decisao foi **reaberta deliberadamente** depois que o painel de admin (que usa auth/gestao de usuarios de verdade) passou a existir, e o usuario pediu explicitamente um framework "mais confiavel e mais aceito pelo mercado". A migracao para Django + Templates + HTMX foi planejada (plano completo em `/home/ricardo/.claude/plans/planeje-como-seria-migrar-buzzing-coral.md`), implementada, testada e colocada no lugar do FastAPI+Reflex, que foi removido do repositorio (ainda recuperavel no historico do git, commit `9335ff1` e anteriores, se precisar).

**Decisao de arquitetura Django:** sem Django REST Framework, sem SPA separada (React) — Templates server-side + HTMX pra trocas parciais (evita reload completo em acoes como aprovar/rejeitar reporte, responder o quiz). Sem Alpine.js: o fluxo do quiz (unico ponto que precisaria de estado no cliente) usa **sessao do servidor** (`request.session["quiz_question_ids"]`/`["quiz_answers"]`) — cada resposta e' um `hx-post` que troca so' o card da pergunta, HTMX nao guarda nenhum estado proprio.

## Comandos

```bash
# Subir tudo (Postgres+pgvector, Ollama, Django) via Docker
cp .env.example .env
docker compose up --build
# App: http://localhost:8000

# Local sem Docker
cd questionario_django
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env               # editar ADMIN_EMAILS/GOOGLE_CLIENT_ID se necessario
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
pytest                             # todos os testes, sem skip automatico (Postgres+pgvector precisa estar acessivel)
pytest apps/questions/tests/test_similarity.py -v -k nome_do_teste   # um teste especifico
```

Variaveis de ambiente completas em `.env.example` — `SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` nunca devem ser hardcoded no codigo (valor efetivo mora em `AppSettings`, ver abaixo).

## Arquitetura

```
questionario_django/
├── manage.py
├── config/                  # settings.py (le .env via python-dotenv), urls.py raiz, wsgi.py
├── apps/
│   ├── core/                 # AppSettings (linha unica id=1), permissions.py (admin_required/is_admin_email
│   │                         #   por ADMIN_EMAILS), design system CSS (static/core/css/), HTMX vendorizado
│   │                         #   (static/core/js/), templates/core/base.html + navbar/admin_nav
│   ├── accounts/              # User custom (AbstractBaseUser+PermissionsMixin, sem coluna role),
│   │                         #   login/registro/conta, Google login, gestao de usuarios (admin)
│   ├── questions/              # Question (embedding VectorField(768) + HnswIndex), dedupe semantico
│   ├── quiz/                   # QuizAttempt, fluxo de resposta via sessao do servidor + HTMX
│   └── moderation/              # Report, fila de moderacao, aprovar/rejeitar remocao em lote,
│                               #   dashboard, configuracoes (3 thresholds em runtime)
├── Dockerfile                 # collectstatic no build + gunicorn/whitenoise em producao (DEBUG=false)
└── conftest.py + tests/        # fixtures compartilhadas (fake_embedding) + testes de fluxo cross-app
```

Cada app tem seu proprio `services.py` (logica de decisao pura, sem tocar ORM/request — `filter_by_threshold`, `should_flag`, `score_quiz`, `compute_average_score_percent`, `compute_user_reputation`/`compute_all_users_reputation`, `compute_stats`) e `tests/` (unitarios puros + smoke de paginas). Ao adicionar regra de negocio nova, prefira esse padrao em vez de misturar decisao com a query no ORM.

**Fluxo critico (RF02/RF05 — dedupe semantica):** `questions.views.create_question` chama `services.get_embedding` (Ollama, cliente sincrono `httpx.post`, ver "Ollama sincrono" abaixo) → `services.find_similar_active_questions` busca vizinhos via `CosineDistance("embedding", ...)` do `pgvector.django` (indice HNSW, `vector_cosine_ops`) só em `status=active` → se similaridade `>= SIMILARITY_THRESHOLD` (valor efetivo em `AppSettings`), a mesma pagina e' re-renderizada com a lista de perguntas parecidas em vez de salvar (via HTMX, troca só o `#question-form-wrapper`).

**Moderacao (RF04):** `moderation.views.report_question` grava o `Report` (um por par question+reporter — `UniqueConstraint`, view checa antes de criar) e `services.register_report` verifica a contagem; ao atingir `REPORT_THRESHOLD`, muda `Question.status` para `reported` — isso so' controla se a pergunta sai do pool do quiz (`quiz.services.pick_random_questions` so' seleciona `status=active`), **nao** controla o que o admin ve na fila de moderacao (ver abaixo).

`ReportForm` (`apps/moderation/forms.py`) exige `reason_category` (uma de `REASON_CATEGORY_CHOICES`) e so' exige `reason` (texto livre) quando `reason_category == "Outro"` — validado no metodo `clean()` do form (cross-field), nao em campos separados. `Report.reason` e' `null=True` no model por causa disso.

A fila de moderacao (`moderation.views.pending_reports`, `services.list_questions_with_pending_reports`) lista perguntas com **pelo menos 1 `Report.status=pending`**, independente do status da pergunta — de proposito, diferente de `status=reported`, pra um reporte nunca ficar "preso" inacessivel so' porque a pergunta ja saiu desse status (ex: foi removida antes do reporte ser resolvido). Tambem mostra reportes desde o primeiro, antes do auto-flag por `REPORT_THRESHOLD`.

O admin resolve uma pergunta reportada com UMA decisao que cobre a pergunta e TODOS os reportes pendentes dela de uma vez (`services.resolve_reported_question`, views `approve_removal`/`reject_removal`, botoes com `hx-post` que trocam so' o card da pergunta na fila) — nao ha decisao por reporte individual:
- **Aprovar Remocao:** `Question.status = removed` + todo `Report.status=pending` daquela pergunta vira `accepted` (credita quem reportou).
- **Rejeitar Remocao:** `Question.status = active` + os mesmos reportes viram `rejected`.

A tela de moderacao mostra quem criou a pergunta e quem reportou (nome + motivo), mas nao tem edicao inline — editar so' existe na aba "Perguntas Removidas" (`services.update_question`, recalcula embedding se o enunciado mudar, edicao inline via `hx-get`/`hx-post` trocando o card por um form e vice-versa). Uma pergunta ja removida pode ser reativada e editada la (`services.approve_question` — reativa sem mexer em reportes, que ja foram resolvidos quando a pergunta foi removida). Reportes aceitos/rejeitados e perguntas removidas alimentam a reputacao de quem reportou/criou, calculada na hora (`services.compute_user_reputation`), exposta em `accounts.views.my_stats` (pagina "Estatisticas" do aluno) e em `accounts.views.admin_user_list` (visao do admin, via `compute_all_users_reputation` pra evitar N+1).

**Admin da aplicacao (painel do professor):** quem esta em `settings.ADMIN_EMAILS` (.env, lista separada por virgula) vira admin — nao ha coluna `role` nem fluxo de auto-promocao, verificado via decorator `apps.core.permissions.admin_required`/`is_admin_email`, exposto em todo template via context processor `apps.core.context_processors.admin_flag` (nunca expõe a lista de e-mails pro template, so' o booleano `is_admin`). `SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` no `.env` sao so' o default inicial (seed na migration `core/0001_initial.py`) — o valor efetivo mora no model `AppSettings` (linha unica, `pk=1`, `get_solo()`) e e' editavel via `moderation.views.admin_settings`; `questions/services.py`, `quiz/services.py` e `moderation/services.py` leem de la (`core.services.get_effective_settings()`), nunca de `settings` estatico direto pra esses 3 campos.

**Django Admin nativo (`/django-admin/`):** registrado so' pra `accounts.User` (gestao de usuarios, `UserAdmin`), `questions.Question` e `moderation.Report` (inspecao ad-hoc pelo professor/dev). **Atencao:** usa a sessao de auth nativa do Django (superuser via `createsuperuser`), uma credencial **separada** de "email em `ADMIN_EMAILS`" (admin da aplicacao) — nao confundir os dois conceitos, sao logins e propositos diferentes. `pgvector.django.VectorField` retorna um array numpy — colocar o campo `embedding` direto em `readonly_fields` quebra com `ValueError: The truth value of an array... is ambiguous` (o `display_for_field` do admin faz `value in field.empty_values`); a solucao usada foi `exclude = ("embedding",)` + um metodo custom (`embedding_preview`) em `readonly_fields` que converte pra string antes (ver `apps/questions/admin.py` e o teste de regressao `apps/questions/tests/test_admin.py`).

**Login com Google (opcional, aditivo):** `accounts.views.google_login` recebe o id_token do Google (`credential`, via form POST do botao Google Identity Services, JS vanilla do proprio Google, sem lib Python de frontend), verifica assinatura/audience/expiracao via `google-auth` (`accounts.services.verify_google_id_token`, audience = `GOOGLE_CLIENT_ID`) e cria a sessao Django com `django.contrib.auth.login()` — nao ha JWT nem estado paralelo. Resolve o usuario por `google_sub` e, se nao achar, por `email` (linka a conta existente em vez de duplicar); so' cria usuario novo se nenhum dos dois bater. Contas so'-Google usam `user.set_unusable_password()` (convencao nativa do Django) em vez de `hashed_password=None` como no SQLAlchemy antigo — o efeito observavel e' o mesmo (`check_password` sempre falha pra essas contas), entao `login()` por email/senha nao precisa de nenhum tratamento especial. Sem `GOOGLE_CLIENT_ID` configurado, o botao nao aparece (`{% if google_client_id %}` no template) — feature desligada, resto do app intacto. **Atencao ao testar:** o Google Identity Services valida a *origin* exata (protocolo+host+porta) contra a lista de "Authorized JavaScript origins" configurada no Google Cloud Console pro Client ID — se a porta/dominio mudar, precisa atualizar essa lista la, senao o botao aparece mas o login falha silenciosamente.

**Ollama sincrono (nao async):** `questions.services.get_embedding` usa `httpx.post` sincrono (nao `httpx.AsyncClient`) porque as views sao Django comuns (sync), nao ha DRF nem necessidade de ASGI so' por causa dessa chamada — o bloqueio do worker durante a chamada e' aceitavel com multiplos workers (`gunicorn -w N`) e volume baixo de criacao de perguntas (projeto academico). `google.auth.transport.requests` (usado por `verify_google_id_token`) exige o pacote `requests` instalado separadamente — nao vem como dependencia transitiva do `google-auth`, mesmo sendo importado por ele.

**`pgvector.django`:** `VectorField(dimensions=1024)` + `HnswIndex` em `Meta.indexes` (com `m=16, ef_construction=64, opclasses=["vector_cosine_ops"]`) **e'** reconhecido pelo `makemigrations`, que gera a `AddIndex` sozinho — nao precisa de SQL manual pro indice. A extensao `vector` do Postgres precisa de operacao manual (`pgvector.django.VectorExtension()`, adicionada a mao na migration inicial gerada, ver `apps/questions/migrations/0001_initial.py`). Os enums de status (`QuestionStatus`, `ReportStatus`) sao `models.TextChoices` — viram `varchar`+`choices` no banco (validacao so' em nivel de aplicacao), nao um tipo `ENUM` nativo do Postgres.

**Trocar o modelo de embedding (ja aconteceu uma vez: `nomic-embed-text` 768d → `bge-m3` 1024d, 2026-09-20):** motivo — `nomic-embed-text` dava similaridade alta (~0.82) pra perguntas com o mesmo molde gramatical mas fatos diferentes (ex: "a capital do Brasil e Brasilia" vs "a capital da Franca e Paris"), quase colando no valor de parafrases reais (~0.98) e deixando pouca margem pra calibrar o threshold. Testado empiricamente (nao so' por ranking de leaderboard — `multilingual-e5-large-instruct`, #1 em STS-PT no MTEB, na pratica separou pior que `bge-m3` aqui) com 3 pares de frase (parafrase / mesmo-molde-fatos-diferentes / sem-relacao) em 5 modelos via Ollama `/api/embeddings` direto, comparando o "gap" de cosseno entre parafrase e falso-positivo. `bge-m3` venceu (gap 0.31 vs 0.16 do `nomic-embed-text`). Trocar modelo de embedding exige SEMPRE mudar 4 coisas juntas, nunca so' o nome: `EMBEDDING_DIM` em `apps/questions/models.py`, uma migration de `AlterField` na coluna `embedding` (**em migration SEPARADA de qualquer `RunPython` que apague/limpe dados antes** — Postgres nao permite `DELETE` que dispara trigger de FK e `ALTER TABLE` na mesma transacao, erro real: "cannot ALTER TABLE because it has pending trigger events"), o `OLLAMA_EMBED_MODEL` no `.env`, e o `SIMILARITY_THRESHOLD` (a escala de similaridade muda de modelo pra modelo). `apps/questions/management/commands/recompute_embeddings.py` recalcula o embedding de perguntas existentes com o modelo atual — rodar depois de qualquer troca de modelo se houver dado real a preservar (da vez que isso aconteceu, so' havia 1 pergunta de teste, entao a migration simplesmente apagou as perguntas em vez de recalcular).

**Numeros e locale:** `LANGUAGE_CODE = "pt-br"` faz o filtro de template `floatformat` exibir numeros com virgula decimal (ex: "0,98" na exibicao informativa de similaridade) — mas os campos de formulario (`FloatField`/`IntegerField` em `AppSettingsForm`) continuam esperando ponto, porque tem `localize=False` por padrao no Django. Isso **nao e' um bug** (confirmado testando o POST em `/admin/configuracoes`), so' uma inconsistencia cosmetica entre texto informativo (locale-aware) e campo editavel (sempre ponto).

**Producao:** estaticos servidos via `whitenoise` (`STORAGES["staticfiles"] = "whitenoise.storage.CompressedManifestStaticFilesStorage"`), sem precisar de nginx separado — `collectstatic` roda no build da imagem Docker (`questionario_django/Dockerfile`). `.env` na raiz do repo e' lido tanto pelo `docker-compose.yml` (interpolacao de variaveis) quanto por `python-dotenv` dentro do container (`config/settings.py::load_dotenv`) — nao precisa exportar nada manualmente.

## Testes

`questionario_django/` (raiz do projeto Django) tem duas categorias, todas via `pytest`+`pytest-django`:
- **Unitarios** (`apps/*/tests/test_*.py` cobrindo `services.py` de cada app): puros, sem `@pytest.mark.django_db`, rodam em qualquer lugar sem banco.
- **Integracao** (`tests/test_integration_flow.py`, `tests/test_pages_render.py`, `apps/questions/tests/test_admin.py`): usam `@pytest.mark.django_db` + `django.test.Client` contra um Postgres+pgvector real — **sem skip automatico** (diferente do `requires_db` que o backend antigo tinha; aqui presume-se que o Postgres de dev/CI esta acessivel). `conftest.py` (raiz) fixa `ADMIN_EMAILS={"admin@example.com"}` e desliga `RATELIMIT_ENABLE` via fixture `autouse`; a fixture `fake_embedding` faz `monkeypatch.setattr("apps.questions.services.get_embedding", ...)` com um embedding deterministico por hash simples do texto, pra nao depender do Ollama real nesses testes (view e `moderation.services.update_question` sempre chamam `services.get_embedding` — nunca importam o nome solto — exatamente pra esse monkeypatch pegar os dois pontos de chamada).

## Especificacao de requisitos (referencia)

Requisitos funcionais e nao funcionais originais do projeto — uteis para checar se uma mudanca ainda atende ao escopo do MVP. Sao independentes da stack de implementacao (foram escritos quando o projeto era FastAPI+Reflex, continuam validos com Django).

### Visao geral do produto

Plataforma web onde alunos se cadastram, criam perguntas de Verdadeiro ou Falso sobre qualquer conteúdo de estudo, e respondem questionários montados aleatoriamente a partir do banco de perguntas de todos os usuários. O sistema evita duplicação semântica de perguntas usando embeddings + busca vetorial.

### Requisitos Funcionais (RF)

**RF01 — Cadastro e autenticação**
- Aluno se cadastra com nome, e-mail e senha.
- Login com e-mail/senha (sessao do Django, cookie httpOnly).
- Login alternativo com Google (opcional/aditivo, adicionado após o MVP) -- cria ou vincula a conta pelo e-mail, sem exigir senha.
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
- Usuário pode reportar uma pergunta como incorreta/problemática, com tipo de problema **obrigatório** (lista fechada: resposta incorreta, enunciado ambíguo ou confuso, conteúdo ofensivo ou inadequado, pergunta duplicada, fora do tema, outro) + motivo (texto livre) **opcional**, exceto quando o tipo é "outro" (aí o texto livre é obrigatório — é a única pista do motivo real).
- Um usuário só pode reportar a mesma pergunta uma vez.
- Reportes ficam associados à pergunta e ao usuário que reportou, com data.
- Regra de moderação: flag automática para revisão após N reportes (default configurável 3), sem remoção automática definitiva.
- Cada reporte individual é aceito ou rejeitado pelo admin (ação separada de aprovar/remover a pergunta). Reportes aceitos contam para a reputação de quem reportou; perguntas removidas contam como penalidade para quem as criou -- ambos visíveis para o usuário numa página "Estatísticas" e para o admin em Usuários (adicionado após o MVP).

**RF05 — Detecção de similaridade semântica (núcleo técnico)**
- Embedding do enunciado gerado localmente via Ollama (`bge-m3`).
- Embeddings persistidos no Postgres via `pgvector`.
- Busca de vizinhos mais próximos por similaridade de cosseno, limiar configurável (env var/`AppSettings`, nunca hardcoded — default `0.80`).

### Requisitos Não Funcionais (RNF)

- **Stack:** Django (Templates + HTMX), Postgres+pgvector, Ollama local (sem API paga externa).
- **Persistência:** Django ORM + migrations versionadas.
- **Segurança:** senhas com hash forte (bcrypt via `BCryptSHA256PasswordHasher`), validação de entrada em todos os formulários (Django Forms). Rate limiting em login/registro e criação de pergunta via `django-ratelimit` (5/min e 20/min por IP). CSRF via `{% csrf_token %}` + header `X-CSRFToken` nas requisições HTMX.
- **Performance:** índice `hnsw` no pgvector para a busca vetorial; geração de embedding é síncrona (ver "Ollama sincrono" acima).
- **Testes:** unitários para threshold de similaridade, seleção aleatória/scoring; integração para os principais fluxos (ver seção "Testes").
- **Observabilidade:** `/health` verificando Postgres e Ollama.
- **Containerização:** `docker-compose.yml` orquestra Django, Postgres+pgvector e Ollama; variáveis de ambiente via `.env`.
- **Usabilidade:** fluxo de quiz responsivo em mobile; mensagens de erro claras (ex: pergunta duplicada mostra a pergunta similar).

### Fora de escopo (MVP)

- Gamificação (ranking, pontos, badges).
- Perguntas em formatos além de V/F (múltipla escolha etc.).
- Recuperação de senha (fluxo de e-mail) — fase 2.
- Tabela de auditoria dedicada para ações do admin (hoje é só log estruturado, sem histórico consultável).

### Painel de admin (professor) — adicionado após o MVP

Requisito posterior ao MVP inicial: `role`-free (via `ADMIN_EMAILS`), moderação de perguntas reportadas (aprovar/remover/editar com recálculo de embedding), gestão de usuários (listar + excluir), dashboard (totais, taxa média de acerto via `QuizAttempt`, perguntas/reportes por categoria), e os 3 thresholds de negócio editáveis em runtime. Ver seção "Arquitetura" acima para os arquivos.

Adicionado depois disso: login opcional com Google (ver seção "Login com Google" acima) e veredito individual por reporte (aceitar/rejeitar, alimentando a reputação do usuário -- ver seção "Moderação (RF04)" acima).

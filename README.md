# Questionario

Sistema web de apoio a educacao onde alunos criam e respondem perguntas de Verdadeiro/Falso, com deduplicacao semantica via embeddings (Ollama + pgvector) e moderacao automatica por reportes.

## Stack

- **Backend + Frontend:** Django (monolito) — Templates server-side + HTMX para trocas parciais de tela (sem SPA, sem Django REST Framework)
- **Banco:** PostgreSQL + extensao `pgvector` (indice HNSW, distancia de cosseno), via `pgvector.django`
- **Embeddings:** Ollama rodando localmente, modelo `bge-m3`
- **Autenticacao:** sessao do Django (cookie `sessionid`, httpOnly)

## Rodando com Docker (recomendado)

```bash
cp .env.example .env   # ajuste os valores se necessario
docker compose up --build
```

Isso sobe: Postgres com pgvector, Ollama (baixando o modelo `bge-m3` automaticamente via o servico `ollama-init`) e a aplicacao Django.

- App: http://localhost:8000
- Healthcheck: http://localhost:8000/health
- Django Admin (inspecao ad-hoc, precisa de superuser via `createsuperuser`): http://localhost:8000/django-admin/

## Variaveis de ambiente

Ver `.env.example`. Nenhum valor de negocio (limiar de similaridade, tamanho do questionario, limiar de reportes) e hardcoded — tudo vem de env vars:

| Variavel | Descricao | Default |
|---|---|---|
| `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` | Credenciais do Postgres | `questionario`/`questionario`/`questionario_django` |
| `OLLAMA_HOST` | URL do servidor Ollama | `http://ollama:11434` |
| `OLLAMA_EMBED_MODEL` | Modelo de embedding usado | `bge-m3` |
| `SIMILARITY_THRESHOLD` | Limiar de similaridade de cosseno para descartar pergunta duplicada | `0.80` |
| `QUIZ_SIZE` | Quantidade de perguntas por questionario | `10` |
| `REPORT_THRESHOLD` | Quantidade de reportes para flagar uma pergunta | `3` |
| `DJANGO_SECRET_KEY` | Chave secreta do Django (sessao, CSRF) | - |
| `DJANGO_DEBUG` | Modo debug (nunca `true` em producao) | `false` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por virgula | `localhost,127.0.0.1` |
| `ADMIN_EMAILS` | E-mails (separados por virgula) com acesso ao painel de admin | vazio |
| `GOOGLE_CLIENT_ID` | Client ID OAuth do Google, habilita o botao "Entrar com Google" | vazio (feature desligada) |

`SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` no `.env` sao so o valor **inicial** (semeado na primeira migration) — depois do primeiro boot, esses 3 ficam editaveis em runtime pelo painel de admin (`/admin/configuracoes`), sem precisar reiniciar o container.

## Desenvolvimento local (sem Docker)

```bash
cd questionario_django
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # o Django le esse arquivo automaticamente (python-dotenv)
python manage.py migrate
python manage.py runserver
```

### Testes

```bash
cd questionario_django
pytest                                          # roda tudo (precisa de Postgres+pgvector acessivel)
pytest apps/questions/tests/test_similarity.py -v   # rodar um arquivo/teste especifico
```

`conftest.py` (raiz do projeto Django) fixa `ADMIN_EMAILS` e desliga o rate limiting nos testes; a fixture `fake_embedding` substitui a chamada real ao Ollama por um embedding deterministico.

### Migrations

```bash
cd questionario_django
python manage.py makemigrations   # nova migration
python manage.py migrate          # aplicar
```

### Superuser (Django Admin nativo, inspecao ad-hoc)

```bash
cd questionario_django
python manage.py createsuperuser
```

**Atencao:** o superuser do Django Admin (`/django-admin/`) e' uma credencial **separada** do admin da aplicacao (que e' so' "email em `ADMIN_EMAILS`", sem cadastro especial) — sao dois logins e propositos diferentes.

## Fluxo critico (dedupe semantica)

Ao criar uma pergunta: o sistema gera o embedding do enunciado via Ollama, busca as perguntas ativas mais proximas por similaridade de cosseno no pgvector (indice HNSW) e, se a similaridade for `>= SIMILARITY_THRESHOLD`, descarta a pergunta e reexibe a mesma pagina com a(s) pergunta(s) similar(es) (via HTMX, sem reload completo); caso contrario, persiste a pergunta com seu embedding.

## Login com Google (opcional)

Alem do login por e-mail/senha, ha um botao "Entrar com Google" nas paginas de login e cadastro. E' puramente aditivo: nao muda o fluxo existente, so cria/vincula a conta pelo e-mail da conta Google. Requer criar um OAuth Client ID em https://console.developers.google.com/apis/credentials, configurar `GOOGLE_CLIENT_ID` no `.env`, e adicionar a origem (protocolo+host+porta onde a app roda) na lista de "Authorized JavaScript origins" desse Client ID no Google Cloud Console — sem isso o botao aparece mas o login falha. Sem `GOOGLE_CLIENT_ID` definido, o botao nem aparece -- o resto do app funciona normal.

## Moderacao

Cada reporte em uma pergunta e contabilizado; ao atingir `REPORT_THRESHOLD` reportes, a pergunta muda de status para `reported` e sai do pool de perguntas ativas usadas nos questionarios (sem remocao automatica definitiva). Um usuario so pode reportar a mesma pergunta uma vez. O tipo de problema (lista fechada: resposta incorreta, enunciado ambiguo, conteudo ofensivo, duplicada, fora do tema, outro) e' obrigatorio; o motivo em texto livre e' opcional, exceto quando o tipo e' "outro".

A fila de moderacao (`/admin/moderacao`) lista perguntas com reporte pendente, independente do status delas -- nao so as que ja atingiram `REPORT_THRESHOLD`. O admin resolve com uma decisao so por pergunta: **Aprovar Remocao** (remove a pergunta, aceita os reportes pendentes) ou **Rejeitar Remocao** (mantem/reativa a pergunta, rejeita os reportes pendentes) -- ambas via HTMX, sem reload da pagina. Uma pergunta removida pode ser reativada e editada na aba "Perguntas Removidas". Reportes aceitos contam pra reputacao de quem reportou; perguntas removidas contam como penalidade pra quem criou a pergunta -- os dois numeros ficam visiveis pro proprio usuario na pagina "Estatisticas" e pro admin em Usuarios.

## Concorrencia e rate limiting

- **Rate limiting:** login/registro (5/minuto por IP) e criacao de pergunta (20/minuto por IP), via `django-ratelimit`. Excede o limite -> `429 Too Many Requests`.
- Gargalo esperado sob carga: geracao de embedding no Ollama e' a operacao mais pesada (CPU-bound, sem GPU) — perguntas criadas em rajada ficam mais lentas para salvar, mas nao travam o sistema (multiplos workers gunicorn absorvem o paralelismo).

## Painel de admin (professor)

Quem estiver listado em `ADMIN_EMAILS` vira admin automaticamente ao logar (sem cadastro especial, sem coluna de role no banco). Acesso em `/admin`:

- **Visao Geral** (`/admin`) — totais de usuarios/perguntas/reportes, taxa media de acerto, perguntas e reportes por categoria.
- **Moderacao** (`/admin/moderacao`) — lista perguntas com reporte pendente (mostra resposta cadastrada e quem reportou), Aprova Remocao/Rejeita Remocao (decisao unica que resolve a pergunta e todos os reportes pendentes dela).
- **Perguntas Removidas** (`/admin/removidas`) — lista perguntas removidas, com opcao de editar (inline, via HTMX) e reativar (volta pra `active`).
- **Usuarios** (`/admin/usuarios`) — lista com contagem de perguntas por usuario, reputacao (reportes aceitos/rejeitados, perguntas removidas), exclusao de conta (nao permite excluir a propria conta admin por ali).
- **Configuracoes** (`/admin/configuracoes`) — edita `SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` em runtime.

## Fora do escopo do MVP

- Recuperacao de senha (fluxo por e-mail) — fase 2
- Gamificacao (ranking, pontos, badges)
- Perguntas em formatos alem de V/F
- Tabela de auditoria dedicada para acoes do admin (hoje fica so no log estruturado)

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
- Mailpit (caixa de entrada falsa com os e-mails de codigo, so' dev): http://localhost:8025
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
| `EMAIL_HOST`/`EMAIL_PORT`/`EMAIL_USE_TLS` | SMTP dos e-mails de codigo. Vazio = e-mail sai no console (so' dev) | `mailpit`/`1025`/`false` no Docker |
| `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` | Credenciais SMTP (Gmail: senha de app) | vazio |
| `GUNICORN_WORKERS` | Processos gunicorn atendendo requests em paralelo | `4` |
| `TRUSTED_PROXY_COUNT` | Numero de proxies confiaveis na frente do Django (IP real pelo `X-Forwarded-For`) | `0` |
| `EMAIL_SEND_ASYNC` | Envia os e-mails em background (a tela nao espera o SMTP) | `true` |
| `DEFAULT_FROM_EMAIL` | Remetente (no Gmail, tem que ser o mesmo e-mail do `EMAIL_HOST_USER`) | `Questionario <nao-responda@localhost>` |

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

## Quiz de treino e comentarios

No questionario, o aluno responde e ve na hora se acertou, a resposta correta e as referencias da questao; so' avanca quando clica em **Proxima**. Depois de responder aparecem **Comentarios** (le e escreve, dentro do proprio card) e **Reportar**. Depois do quiz, a aba **Minhas interacoes** lista as questoes em que ele comentou (com selo de comentarios novos) e os reportes que ele fez. Alunos podem reportar comentarios; o admin decide na aba **Comentarios reportados**.

## Moderacao

Cada reporte em uma pergunta e contabilizado; ao atingir `REPORT_THRESHOLD` reportes, a pergunta muda de status para `reported` e sai do pool de perguntas ativas usadas nos questionarios (sem remocao automatica definitiva). Um usuario so pode reportar a mesma pergunta uma vez. O aluno sempre escreve o motivo do reporte (campo de texto obrigatorio, sem lista de tipos); o mesmo vale para reportar um comentario.

A fila de moderacao (`/admin/moderacao`) lista perguntas com reporte pendente, independente do status delas -- nao so as que ja atingiram `REPORT_THRESHOLD`. O admin resolve com uma decisao so por pergunta: **Aprovar Remocao** (remove a pergunta, aceita os reportes pendentes) ou **Rejeitar Remocao** (mantem/reativa a pergunta, rejeita os reportes pendentes) -- ambas via HTMX, sem reload da pagina. Uma pergunta removida pode ser reativada e editada na aba "Perguntas Removidas". Reportes aceitos contam pra reputacao de quem reportou; perguntas removidas contam como penalidade pra quem criou a pergunta -- os dois numeros ficam visiveis pro proprio usuario na pagina "Estatisticas" e pro admin em Usuarios.

## Confirmacao de e-mail

O cadastro so' cria a conta depois que o aluno digita o codigo de 6 digitos enviado por e-mail (vale 15 min, 5 tentativas, reenvio a cada 60 s e no maximo 5 envios/hora por e-mail). Trocar o e-mail na pagina Conta tambem exige o codigo enviado ao novo e-mail, e o e-mail antigo recebe um aviso.

- **Dev (Docker):** os e-mails caem no Mailpit, em http://localhost:8025 -- nada sai pra internet.
- **Producao com Gmail:** crie uma conta Gmail so' pro sistema, ative a verificacao em 2 etapas, gere uma senha de app em https://myaccount.google.com/apppasswords e troque no `.env` o bloco de e-mail pelo bloco do Gmail (comentado no `.env.example`). Reinicie o container `django`. Sem `EMAIL_HOST` em producao, o codigo iria pro log -- sempre configure o SMTP.

## Alterar e-mail ou senha (pagina Conta)

O nome pode ser alterado direto. Para alterar o e-mail ou a senha, o aluno clica em "Enviar codigo para alterar e-mail ou senha", recebe um codigo no e-mail atual e, depois de digita-lo, tem 10 minutos para fazer as alteracoes. Trocar o e-mail ainda pede o codigo enviado ao novo e-mail; trocar a senha desconecta as outras sessoes e manda um aviso por e-mail.

## Recuperacao de senha

"Esqueci minha senha" na tela de login: o aluno informa o e-mail ou a matricula e recebe, no e-mail cadastrado na conta, um codigo de 6 digitos (mesmas regras do codigo do cadastro). Na tela seguinte, digita o codigo e a nova senha; a senha e' trocada, ele entra logado, as outras sessoes abertas da conta sao desconectadas e chega um e-mail avisando da troca. A resposta e' sempre a mesma, exista ou nao conta com aquele e-mail.

## Concorrencia e rate limiting

- **Rate limiting** (`django-ratelimit`, regras em `apps/core/ratelimits.py`): por **alvo**, nao por IP -- login e cadastro 5/minuto por e-mail, recuperacao de senha 5/minuto por e-mail/matricula, codigos na Conta por usuario, criacao de pergunta 20/minuto por usuario. Por IP so' um teto alto (300/minuto nas telas de conta, 1000/minuto na criacao de pergunta), pra turma inteira atras do mesmo IP da universidade nao ser bloqueada. Excede o limite -> `429 Too Many Requests`. Com proxy (nginx, Cloudflare) na frente, defina `TRUSTED_PROXY_COUNT` no `.env` com o numero de proxies.
- **Desempenho:** gunicorn com 4 workers (`GUNICORN_WORKERS`), modelo de embedding sempre carregado no Ollama (`OLLAMA_KEEP_ALIVE=-1`, ~1,2 GB de RAM) e aquecido na subida, e e-mails enviados em background.
- Gargalo esperado sob carga: geracao de embedding no Ollama e' a operacao mais pesada (CPU-bound, sem GPU) — perguntas criadas em rajada ficam mais lentas para salvar, mas nao travam o sistema (multiplos workers gunicorn absorvem o paralelismo).

## Painel de admin (professor)

Quem estiver listado em `ADMIN_EMAILS` vira admin automaticamente ao logar (sem cadastro especial, sem coluna de role no banco). Acesso em `/admin`:

- **Visao Geral** (`/admin`) — totais de usuarios/perguntas/reportes, taxa media de acerto, perguntas por topico.
- **Moderacao** (`/admin/moderacao`) — lista perguntas com reporte pendente (mostra resposta cadastrada e quem reportou), Aprova Remocao/Rejeita Remocao (decisao unica que resolve a pergunta e todos os reportes pendentes dela).
- **Perguntas Removidas** (`/admin/removidas`) — lista perguntas removidas, com opcao de editar (inline, via HTMX) e reativar (volta pra `active`).
- **Usuarios** (`/admin/usuarios`) — lista com contagem de perguntas por usuario, reputacao (reportes aceitos/rejeitados, perguntas removidas), edicao da matricula e exclusao de conta (nao permite excluir a propria conta admin por ali). O aluno nao exclui a propria conta nem altera a matricula.
- **Configuracoes** (`/admin/configuracoes`) — edita `SIMILARITY_THRESHOLD`, `QUIZ_SIZE` e `REPORT_THRESHOLD` em runtime.

## Fora do escopo do MVP

- Gamificacao (ranking, pontos, badges)
- Perguntas em formatos alem de V/F
- Tabela de auditoria dedicada para acoes do admin (hoje fica so no log estruturado)

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

# Roda como usuario comum, nao root: nada no sistema precisa de privilegio (porta 8000 >
# 1024; so' le o codigo/estaticos e grava em planilhas/). Se alguem explorar uma falha,
# o processo invadido nao tem root no container. UID 1000 = mesmo usuario do servidor,
# entao os arquivos gravados no volume planilhas/ ficam com o dono certo la' (sem sudo).
# Outro UID no servidor: docker compose build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g)
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid "$APP_GID" app \
    && useradd --uid "$APP_UID" --gid "$APP_GID" --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/planilhas \
    && chown app:app /app/planilhas
# --create-home: o gunicorn 26 cria o socket do "control server" dele no $HOME do usuario
# (sem a pasta, loga "Control server error: Permission denied: '/home/app'").
# Codigo e estaticos continuam do root (so' leitura pro app); sem .pyc, que ele nem conseguiria gravar.
ENV PYTHONDONTWRITEBYTECODE=1
USER app

# migrate = migrate_schemas (django-tenants): migrations compartilhadas no schema public e
# depois as das apps por semestre em cada schema de semestre.
# Varios workers: um request esperando Ollama/SMTP nao trava os outros. O cache do
# rate limit e' o DatabaseCache (compartilhado entre workers; createcachetable cria a
# tabela). warm_ollama roda em background pra carregar o modelo de embedding sem
# atrasar a subida do gunicorn.
CMD ["sh", "-c", "python manage.py migrate && python manage.py createcachetable && (python manage.py warm_ollama &) && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${GUNICORN_WORKERS:-4} --timeout ${GUNICORN_TIMEOUT:-60}"]

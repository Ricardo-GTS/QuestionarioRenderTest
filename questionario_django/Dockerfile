FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

# migrate = migrate_schemas (django-tenants): migrations compartilhadas no schema public e
# depois as das apps por semestre em cada schema de semestre.
# Varios workers: um request esperando Ollama/SMTP nao trava os outros. O cache do
# rate limit e' o DatabaseCache (compartilhado entre workers; createcachetable cria a
# tabela). warm_ollama roda em background pra carregar o modelo de embedding sem
# atrasar a subida do gunicorn.
CMD ["sh", "-c", "python manage.py migrate && python manage.py createcachetable && (python manage.py warm_ollama &) && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-4} --timeout ${GUNICORN_TIMEOUT:-60}"]

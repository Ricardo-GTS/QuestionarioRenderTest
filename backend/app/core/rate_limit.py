from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# RNF03: rate limiting basico nos endpoints de criacao de pergunta e login
# (evitar spam/forca bruta). Ver app/main.py para a instalacao do middleware.
LOGIN_RATE_LIMIT = "5/minute"
CREATE_QUESTION_RATE_LIMIT = "20/minute"

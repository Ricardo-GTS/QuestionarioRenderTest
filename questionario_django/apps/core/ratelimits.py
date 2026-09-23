"""Regras de rate limit (django-ratelimit) num lugar so'.

Limite "de verdade" e' por ALVO (e-mail tentado, usuario logado), nao por IP: numa sala
de aula os alunos saem pelo mesmo IP publico (NAT do Wi-Fi da universidade), e um
limite baixo por IP bloquearia a turma inteira a partir do 6o login. Por IP fica so' um
teto alto contra abuso em massa. Tentativas de codigo por e-mail ja' tem limite proprio
(5 por codigo, 60 s entre envios, 5 envios/hora por e-mail -- accounts.services).
"""

from django.conf import settings

# Teto por IP, somando todas as telas de conta (grupo "auth-ip"): folgado pra uma
# turma inteira atras do mesmo NAT fazendo login/cadastro/codigos ao mesmo tempo.
IP_CEILING = "300/m"
# Criacao de pergunta: sem limite pratico por IP (so' o por usuario, abaixo).
QUESTION_IP_CEILING = "1000/m"

PER_TARGET = "5/m"  # por e-mail tentado (login/cadastro) ou por usuario (codigo na Conta)
CODE_CONFIRM_PER_USER = "10/m"
QUESTION_PER_USER = "20/m"


def post_email(group, request) -> str:
    """E-mail do POST normalizado -- 'Aluno@X.com' e 'aluno@x.com ' contam juntos."""
    return request.POST.get("email", "").strip().lower()


def post_identifier(group, request) -> str:
    """E-mail ou matricula da recuperacao de senha, normalizado."""
    return request.POST.get("identifier", "").strip().lower()


def client_ip(request) -> str:
    """IP do cliente pro django-ratelimit (RATELIMIT_IP_META_KEY).

    Sem proxy (TRUSTED_PROXY_COUNT=0, o padrao), usa REMOTE_ADDR. Atras de N proxies
    confiaveis (nginx, Cloudflare...), pega o IP que o proxy mais externo anotou no
    X-Forwarded-For -- NUNCA confiar no header sem proxy na frente, senao o cliente
    forja o proprio IP e foge do limite.
    """
    count = settings.TRUSTED_PROXY_COUNT
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if count > 0 and forwarded:
        hops = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        if len(hops) >= count:
            return hops[-count]
    return request.META["REMOTE_ADDR"]

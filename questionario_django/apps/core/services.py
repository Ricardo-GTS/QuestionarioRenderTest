from django.db import connection

from .models import AppSettings, Semester


def get_effective_settings():
    """Configuracoes de negocio do semestre da requisicao (o schema ativo na conexao).
    Mesmos nomes de campo do antigo AppSettings, entao quem chama nao muda. Sem semestre
    nenhum (instalacao nova), devolve os valores iniciais de AppSettings."""
    tenant = getattr(connection, "tenant", None)
    if isinstance(tenant, Semester):
        return tenant
    from .semesters import active_semester

    return active_semester() or AppSettings.get_solo()


def update_settings(*, similarity_threshold=None, quiz_size=None, report_threshold=None):
    if similarity_threshold is not None and not (0 < similarity_threshold <= 1):
        raise ValueError("similarity_threshold deve estar entre 0 (exclusivo) e 1 (inclusivo)")
    if quiz_size is not None and quiz_size <= 0:
        raise ValueError("quiz_size deve ser maior que zero")
    if report_threshold is not None and report_threshold <= 0:
        raise ValueError("report_threshold deve ser maior que zero")

    obj = get_effective_settings()
    if similarity_threshold is not None:
        obj.similarity_threshold = similarity_threshold
    if quiz_size is not None:
        obj.quiz_size = quiz_size
    if report_threshold is not None:
        obj.report_threshold = report_threshold
    obj.save()
    return obj

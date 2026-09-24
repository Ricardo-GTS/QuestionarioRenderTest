from django.conf import settings
from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class AppSettings(models.Model):
    """Valores INICIAIS dos 3 thresholds pro primeiro semestre de uma instalacao nova.
    Os valores efetivos moram em Semester (um conjunto por semestre); este model so'
    semeia o primeiro semestre. (Historico: antes era a linha unica efetiva.)

    As env vars SIMILARITY_THRESHOLD/QUIZ_SIZE/REPORT_THRESHOLD sao so o seed
    inicial (ver migration 0002) -- quem le o valor efetivo sempre chama
    get_solo(), nunca settings.SIMILARITY_THRESHOLD direto.
    """

    SETTINGS_ROW_ID = 1

    similarity_threshold = models.FloatField()
    quiz_size = models.PositiveIntegerField()
    report_threshold = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = self.SETTINGS_ROW_ID
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=cls.SETTINGS_ROW_ID,
            defaults={
                "similarity_threshold": settings.SIMILARITY_THRESHOLD,
                "quiz_size": settings.QUIZ_SIZE,
                "report_threshold": settings.REPORT_THRESHOLD,
            },
        )
        return obj

    def __str__(self):
        return "Configuracoes da aplicacao"


class Semester(TenantMixin):
    """Um semestre = um schema do Postgres (django-tenants). Tabelas de questions/quiz/
    moderation existem uma vez por schema, isoladas; contas ficam em "public".
    As configuracoes de negocio (antes em AppSettings) sao por semestre."""

    name = models.CharField(max_length=20, unique=True)  # ex: "2026.1"
    is_active = models.BooleanField(default=False)
    similarity_threshold = models.FloatField()
    quiz_size = models.PositiveIntegerField()
    report_threshold = models.PositiveIntegerField()
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    auto_create_schema = True
    auto_drop_schema = False  # nunca apaga dados de semestre por acidente

    class Meta:
        ordering = ["-opened_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["is_active"], condition=models.Q(is_active=True), name="uq_one_active_semester"),
        ]

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    """Exigido pelo django-tenants. O sistema escolhe o semestre pelo middleware
    (apps.core.middleware.SemesterMiddleware), nao pelo dominio -- um registro por semestre."""


class Enrollment(models.Model):
    """Vinculo aluno x semestre. Conta e' unica (schema public); participar de um
    semestre e' ter um Enrollment nele."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name="enrollments")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "semester"], name="uq_enrollment_user_semester")]

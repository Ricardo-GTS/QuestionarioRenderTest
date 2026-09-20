from django.conf import settings
from django.db import models


class AppSettings(models.Model):
    """Linha unica (id=1) com os 3 thresholds de negocio efetivos em runtime.

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

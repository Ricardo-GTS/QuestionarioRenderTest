from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Question
from .sheets import schedule_sheet_update


@receiver(post_save, sender=Question)
@receiver(post_delete, sender=Question)
def update_backup_sheet(sender, instance, **kwargs):
    """Toda mudanca de questao regenera a planilha de backup do semestre (depois do
    commit, em segundo plano). Mudancas em massa via .update() nao disparam signal e
    chamam schedule_sheet_update() direto (moderation.services rename/delete_topic)."""
    schedule_sheet_update()

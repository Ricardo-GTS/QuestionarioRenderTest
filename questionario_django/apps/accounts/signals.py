from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def enroll_new_user_in_active_semester(sender, instance, created, **kwargs):
    """Toda conta nova (cadastro, Google, createsuperuser, importacao) ja' nasce
    vinculada ao semestre ativo -- so' conta antiga ve a tela "Participar"."""
    if not created:
        return
    from apps.core.semesters import active_semester, enroll

    semester = active_semester()
    if semester is not None:
        enroll(instance, semester)

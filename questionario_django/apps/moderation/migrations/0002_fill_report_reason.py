from django.db import migrations

PLACEHOLDER = "(motivo nao informado -- reporte anterior ao motivo obrigatorio)"


def fill_missing_reason(apps, schema_editor):
    Model = apps.get_model("moderation", "Report")
    Model.objects.filter(reason__isnull=True).update(reason=PLACEHOLDER)
    Model.objects.filter(reason="").update(reason=PLACEHOLDER)


class Migration(migrations.Migration):
    """Separada da migration que torna `reason` obrigatorio: Postgres nao deixa UPDATE
    (com trigger de FK pendente) e ALTER TABLE na mesma transacao."""

    dependencies = [
        ("moderation", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(fill_missing_reason, migrations.RunPython.noop),
    ]

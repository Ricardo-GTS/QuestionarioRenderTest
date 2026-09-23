from django.db import migrations, models


def backfill_missing_topic(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    Question.objects.filter(category__isnull=True).update(category="Nao informado")
    Question.objects.filter(category="").update(category="Nao informado")


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0004_question_citations_references_question_pertinence"),
    ]

    operations = [
        migrations.RunPython(backfill_missing_topic, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="question",
            old_name="category",
            new_name="topic",
        ),
        migrations.AlterField(
            model_name="question",
            name="topic",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="question",
            name="citations_references",
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name="question",
            name="pertinence",
            field=models.TextField(),
        ),
    ]

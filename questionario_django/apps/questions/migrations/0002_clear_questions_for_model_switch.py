# Troca de modelo de embedding (nomic-embed-text, 768d -> bge-m3, 1024d, ver
# memoria project_embedding_model_switch_planned.md). Vetores antigos nao tem
# cast valido pra nova dimensao (pgvector nao define um cast 768->1024), entao
# as perguntas existentes sao apagadas aqui -- seriam recriadas com o comando
# `recompute_embeddings` se houvesse dado real a preservar (nao havia, so' uma
# pergunta de teste). Separado da migration seguinte (AlterField) porque o
# Postgres nao permite DELETE (dispara triggers de FK/cascade) e ALTER TABLE
# na mesma transacao ("cannot ALTER TABLE because it has pending trigger
# events").

from django.db import migrations


def clear_existing_questions(apps, schema_editor):
    Question = apps.get_model("questions", "Question")
    Question.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clear_existing_questions, migrations.RunPython.noop),
    ]

"""Migracao unica: leva os dados do layout antigo (tabelas de questions/quiz/moderation
no schema "public") para o schema do primeiro semestre, sem copiar linha nenhuma.

    python manage.py criar_primeiro_semestre 2026.1 --dry-run   # so' mostra o plano
    python manage.py criar_primeiro_semestre 2026.1

Passos (tudo numa transacao -- DDL no Postgres e' transacional, falhou = nada muda):
1. cria o Semester (sem criar schema/migrations automaticos) + Domain, com as
   configuracoes do AppSettings;
2. CREATE SCHEMA e ALTER TABLE ... SET SCHEMA em cada tabela dessas apps (leva junto
   indices -- inclusive o HNSW --, sequences/identity e constraints);
3. cria o django_migrations do schema (copia do historico inteiro) e o django_content_type;
4. migrate_schemas no schema novo (so' confere -- nao deve haver nada pendente);
5. vincula todos os usuarios (menos admins) ao semestre.
FAZER BACKUP ANTES (scripts/backup_db.sh) e ensaiar numa copia do banco.
"""

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

TENANT_APP_LABELS = ("questions", "quiz", "moderation")


def tenant_tables():
    tables = []
    for label in TENANT_APP_LABELS:
        for model in apps.get_app_config(label).get_models(include_auto_created=True):
            if not model._meta.proxy and model._meta.managed:
                tables.append(model._meta.db_table)
    return sorted(set(tables))


class Command(BaseCommand):
    help = "Move os dados do layout antigo (schema public) para o primeiro semestre."

    def add_arguments(self, parser):
        parser.add_argument("name", help='Nome do semestre, ex: "2026.1"')
        parser.add_argument("--dry-run", action="store_true", help="So' mostra o que seria feito.")
        parser.add_argument("--source-schema", default="public", help="Schema de origem (testes).")

    def handle(self, *args, name, dry_run, source_schema, **options):
        from apps.core.models import AppSettings, Domain, Semester
        from apps.core.permissions import is_admin_email
        from apps.core.semesters import NAME_RE, schema_name_for
        from apps.accounts.models import User

        if not NAME_RE.match(name):
            raise CommandError("Use o formato ANO.1 ou ANO.2 (ex: 2026.1).")
        connection.set_schema_to_public()
        if Semester.objects.exists():
            raise CommandError("Ja' existe semestre cadastrado -- este comando so' roda uma vez, na migracao.")
        schema = schema_name_for(name)
        tables = tenant_tables()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND table_name = ANY(%s)",
                [source_schema, tables],
            )
            present = sorted(row[0] for row in cursor.fetchall())
            counts = {}
            for table in present:
                cursor.execute(f'SELECT count(*) FROM "{source_schema}"."{table}"')
                counts[table] = cursor.fetchone()[0]
        missing = sorted(set(tables) - set(present))
        if missing:
            raise CommandError(f"Tabelas ausentes em {source_schema}: {', '.join(missing)} (layout antigo esperado).")

        base = AppSettings.get_solo()
        students = [u for u in User.objects.all() if not is_admin_email(u.email)]
        self.stdout.write(f"Semestre {name} -> schema {schema}")
        self.stdout.write(
            f"Configuracoes: similaridade {base.similarity_threshold}, quiz {base.quiz_size}, reportes {base.report_threshold}"
        )
        for table in present:
            self.stdout.write(f"  mover {source_schema}.{table} ({counts[table]} linhas)")
        self.stdout.write(f"Vincular {len(students)} usuarios (admins de ADMIN_EMAILS ficam de fora).")
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: nada foi alterado."))
            return

        with transaction.atomic():
            semester = Semester(
                name=name,
                schema_name=schema,
                is_active=True,
                similarity_threshold=base.similarity_threshold,
                quiz_size=base.quiz_size,
                report_threshold=base.report_threshold,
            )
            semester.auto_create_schema = False  # o schema vem das tabelas movidas, nao de migrations
            semester.save(verbosity=0)
            Domain.objects.create(domain=f"{schema}.semestre.local", tenant=semester, is_primary=True)
            with connection.cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA "{schema}"')
                for table in present:
                    cursor.execute(f'ALTER TABLE "{source_schema}"."{table}" SET SCHEMA "{schema}"')
                # INCLUDING ALL traz a PK e a coluna identity (sequencia nova); os ids NAO
                # sao copiados -- senao a sequencia nova comecaria em 1 e colidiria na
                # proxima migration.
                cursor.execute(
                    f'CREATE TABLE "{schema}"."django_migrations" (LIKE "{source_schema}"."django_migrations" INCLUDING ALL)'
                )
                # TODAS as linhas: o Django registra no schema de semestre tambem as
                # migrations das apps compartilhadas (so' nao executa), e
                # questions.0001 depende de accounts.0001 -- copiar so' as 3 apps deixa o
                # historico inconsistente (InconsistentMigrationHistory).
                cursor.execute(
                    f'INSERT INTO "{schema}"."django_migrations" (app, name, applied) '
                    f'SELECT app, name, applied FROM "{source_schema}"."django_migrations" ORDER BY id'
                )
                # contenttypes e' a unica app compartilhada que TAMBEM tem tabela por
                # semestre; como as migrations dela ja' estao marcadas, a tabela e' criada
                # aqui (copia da origem, sem os ids -- nada nas apps por semestre aponta pra ela).
                cursor.execute(
                    f'CREATE TABLE "{schema}"."django_content_type" (LIKE "{source_schema}"."django_content_type" INCLUDING ALL)'
                )
                cursor.execute(
                    f'INSERT INTO "{schema}"."django_content_type" (app_label, model) '
                    f'SELECT app_label, model FROM "{source_schema}"."django_content_type" ORDER BY id'
                )
            call_command("migrate_schemas", tenant=True, schema_name=schema, interactive=False, verbosity=0)
            connection.set_schema_to_public()
            from apps.core.models import Enrollment

            Enrollment.objects.bulk_create([Enrollment(user=u, semester=semester) for u in students], ignore_conflicts=True)

        connection.set_tenant(semester)
        with connection.cursor() as cursor:
            for table in present:
                cursor.execute(f'SELECT count(*) FROM "{schema}"."{table}"')
                after = cursor.fetchone()[0]
                if after != counts[table]:
                    raise CommandError(f"Contagem nao bate em {table}: {counts[table]} -> {after}")
        connection.set_schema_to_public()
        self.stdout.write(self.style.SUCCESS(f"Pronto: semestre {name} ativo, {sum(counts.values())} linhas no schema {schema}."))

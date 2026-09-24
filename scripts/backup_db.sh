#!/bin/sh
# Backup completo do banco (todos os semestres + contas) em backups/.
# Roda o pg_dump DENTRO do container do Postgres (mesma versao do servidor -- o
# container do Django nao tem um pg_dump compativel com o Postgres 16). Usuario e
# banco vem das variaveis do proprio container (nao le o .env, que tem valores com
# espaco, como a senha de app do Gmail).
# Uso: scripts/backup_db.sh [nome-opcional]
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
name="${1:-completo}"
file="backups/questionario_${name}_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$file"
echo "Backup salvo em $file ($(du -h "$file" | cut -f1))"

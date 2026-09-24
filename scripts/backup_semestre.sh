#!/bin/sh
# Backup so' de um semestre (o schema dele), sem as contas.
# Uso: scripts/backup_semestre.sh 2026.1
set -eu
cd "$(dirname "$0")/.."
[ $# -eq 1 ] || { echo "Uso: $0 <semestre, ex: 2026.1>"; exit 1; }
schema="s$(echo "$1" | tr '.' '_')"
mkdir -p backups
file="backups/semestre_${1}_$(date +%Y%m%d_%H%M%S).dump"
docker compose exec -T db sh -c "pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --format=custom --schema=$schema" > "$file"
echo "Backup do semestre $1 (schema $schema) salvo em $file ($(du -h "$file" | cut -f1))"

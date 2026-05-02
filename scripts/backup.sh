#!/bin/bash
set -e
BACKUP_DIR=$HOME/backups
mkdir -p "$BACKUP_DIR"

DATE=$(date +%Y-%m-%d_%H%M)
DB=$HOME/wendrink-erp/wendrink.db
DEST="$BACKUP_DIR/wendrink_$DATE.db"

# SQLite-safe бэкап через .backup команду
sqlite3 "$DB" ".backup '$DEST'"

# Сжатие
gzip "$DEST"

# Ротация: оставить 30 дней
find "$BACKUP_DIR" -name "wendrink_*.db.gz" -mtime +30 -delete

echo "Backup OK: $DEST.gz"

# Пример для внешнего бэкапа (B2/S3):
# b2 upload-file --quiet wendrink-backups "$DEST.gz" "$(basename $DEST.gz)"

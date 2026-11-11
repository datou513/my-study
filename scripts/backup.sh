#!/usr/bin/env bash
# 备份：MySQL 全量 + MinIO 业务桶。Milvus 不备份（纯派生，可 reindex 重建）。
set -euo pipefail
cd "$(dirname "$0")/.."

TS="$(date +%Y%m%d-%H%M%S)"
OUT="backup/$TS"
mkdir -p "$OUT"

set -a; source .env; set +a

echo "→ MySQL"
docker compose exec -T mysql \
  mysqldump -uroot -p"${MYSQL_ROOT_PASSWORD}" \
  --single-transaction --routines --databases "${MYSQL_DATABASE}" > "$OUT/mysql.sql"

echo "→ MinIO"
docker run --rm --network kb_default -v "$PWD/$OUT:/backup" --entrypoint sh minio/mc -c \
  "mc alias set local http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}' >/dev/null && \
   mc mirror --overwrite --quiet local/${MINIO_BUCKET_RAW} /backup/${MINIO_BUCKET_RAW}"

echo "✓ 备份完成：$OUT"
echo "  恢复：./scripts/restore.sh $TS"

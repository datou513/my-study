#!/usr/bin/env bash
# 恢复：MySQL + MinIO。恢复后必须跑一次 kb reindex 重建向量。
set -euo pipefail
cd "$(dirname "$0")/.."

TS="${1:?用法: ./scripts/restore.sh 20261110-220000}"
SRC="backup/$TS"
[ -f "$SRC/mysql.sql" ] || { echo "找不到 $SRC/mysql.sql"; exit 1; }

set -a; source .env; set +a

echo "→ MySQL"
docker compose exec -T mysql \
  sh -c "mysql -uroot -p'${MYSQL_ROOT_PASSWORD}' < /dev/stdin" < "$SRC/mysql.sql"

echo "→ MinIO"
docker run --rm --network kb_default -v "$PWD/$SRC:/backup" --entrypoint sh minio/mc -c \
  "mc alias set local http://minio:9000 '${MINIO_ROOT_USER}' '${MINIO_ROOT_PASSWORD}' >/dev/null && \
   mc mirror --overwrite --quiet /backup/${MINIO_BUCKET_RAW} local/${MINIO_BUCKET_RAW}"

echo "✓ 恢复完成。下一步：kb reindex（M0 之后提供），并抽查 /ready"

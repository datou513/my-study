# 踩坑记录

规则：每踩一个坑记一条，四行以内。面试时这比功能列表值钱，也防止自己在同一个地方摔两次。

格式：

```
## YYYY-MM-DD 一句话标题
- 现象：
- 原因：
- 解法：
- 教训：（下次怎么避免）
```

---

## 2026-11-11 MinIO 官方镜像拉不到了
- 现象：`docker pull minio/minio:RELEASE.2024-12-18T13-15-44Z` 报 `pull access denied ... repository does not exist`，不是超时。
- 原因：MinIO 收缩了社区版分发，Docker Hub 上该 tag 已下线（2025 年起）。
- 解法：改用 `milvusdb/minio:RELEASE.2024-12-18T13-15-44Z`，同版本、Milvus 官方也在用。
- 教训：**选依赖不只看功能，还要看它的分发会不会断。** 关键镜像要在 compose 里注明来源与替代方案。

## 2026-11-10 Milvus 与业务共用 MinIO
- 现象：（待验证）
- 原因：Milvus standalone 默认自带一个 minio 容器；我们的 compose 让它指向业务 MinIO，靠
  `MINIO_ACCESS_KEY_ID` / `MINIO_SECRET_ACCESS_KEY` / `MINIO_BUCKET_NAME` 三个环境变量。
- 解法：若 milvus 容器反复重启，先 `docker logs kb-milvus-1`，再退回官方模板（自带 minio）验证。
- 教训：Milvus 的 compose 是版本敏感的，升级前先看官方模板差异。

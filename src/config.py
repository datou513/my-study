from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全部配置来自环境变量 / .env。容器内由 compose 覆盖 host。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 对象存储
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "kbadmin"
    minio_root_password: str = "change-me-minio"
    minio_bucket_raw: str = "kb-raw"
    minio_secure: bool = False

    # 元数据
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_database: str = "kb"
    mysql_user: str = "kb"
    mysql_password: str = "change-me-mysql"

    # 向量
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "kb_blocks"

    # 模型
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    embed_model: str = "BAAI/bge-m3"
    embed_device: str = "cpu"

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

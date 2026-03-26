from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    artifact_base_dir: str = "artifacts"
    sqlite_path: str = "artifacts/app.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    model_config = SettingsConfigDict(env_prefix="PR_AGENTS_", extra="ignore")

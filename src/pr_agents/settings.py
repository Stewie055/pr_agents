from pr_agents.models import IntentMode, LLMProviderName
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    artifact_base_dir: str = "artifacts"
    sqlite_path: str = "artifacts/app.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    intent_mode: IntentMode = IntentMode.FAKE
    llm_provider: LLMProviderName = LLMProviderName.GLM
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "GLM-4.5-Air"
    llm_timeout: float = 30.0

    model_config = SettingsConfigDict(env_prefix="PR_AGENTS_", extra="ignore")

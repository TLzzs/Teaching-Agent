from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["auto", "mock", "azure", "bedrock"] = "auto"
    llm_temperature: float = 0.4

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-10-21"

    bedrock_region: str = "ap-southeast-2"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"


@lru_cache
def get_settings() -> Settings:
    return Settings()

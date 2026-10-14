import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import Settings


@dataclass
class CompletionRequest:
    system: str
    prompt: str
    json_mode: bool = False
    # Structured hints about what is being generated. Real providers ignore them; the mock
    # provider uses them to produce relevant offline content.
    meta: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str

    async def complete(self, request: CompletionRequest) -> str: ...


class AzureOpenAIProvider:
    name = "azure-openai"

    def __init__(self, settings: Settings):
        from openai import AsyncAzureOpenAI

        self._client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
        self._deployment = settings.azure_openai_deployment
        self._temperature = settings.llm_temperature

    async def complete(self, request: CompletionRequest) -> str:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            temperature=self._temperature,
            response_format={"type": "json_object"} if request.json_mode else None,
        )
        return (response.choices[0].message.content or "").strip()


class BedrockProvider:
    name = "aws-bedrock"

    def __init__(self, settings: Settings):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install the bedrock extra: uv sync --extra bedrock") from exc

        self._client = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        self._model_id = settings.bedrock_model_id
        self._temperature = settings.llm_temperature

    async def complete(self, request: CompletionRequest) -> str:
        response = await asyncio.to_thread(
            self._client.converse,
            modelId=self._model_id,
            system=[{"text": request.system}],
            messages=[{"role": "user", "content": [{"text": request.prompt}]}],
            inferenceConfig={"temperature": self._temperature, "maxTokens": 4096},
        )
        blocks = response["output"]["message"]["content"]
        return "".join(block.get("text", "") for block in blocks).strip()


def get_provider(settings: Settings) -> LLMProvider:
    choice = settings.llm_provider
    if choice == "auto":
        choice = "azure" if settings.azure_openai_api_key else "mock"
    if choice == "azure":
        return AzureOpenAIProvider(settings)
    if choice == "bedrock":
        return BedrockProvider(settings)

    from app.llm.mock import MockProvider

    return MockProvider()

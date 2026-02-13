import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    OCI = "oci"
    LOCAL = "local"


class LLMAdapter(ABC):
    @abstractmethod
    async def create_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def stream_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Any:
        raise NotImplementedError

    async def parse_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_model: Any,
    ) -> Any:
        raise NotImplementedError(
            f"Structured parse is not implemented for provider: {self.__class__.__name__}"
        )


class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    async def create_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if response_format is not None:
            params["response_format"] = response_format
        return await self._client.chat.completions.create(**params)

    async def stream_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Any:
        return await self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

    async def parse_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_model: Any,
    ) -> Any:
        return await self._client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_model,
        )


class GeminiAdapter(LLMAdapter):
    async def create_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        raise NotImplementedError("Gemini adapter is not implemented yet.")

    async def stream_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Any:
        raise NotImplementedError("Gemini adapter is not implemented yet.")


class OCIAdapter(LLMAdapter):
    async def create_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        raise NotImplementedError("OCI adapter is not implemented yet.")

    async def stream_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Any:
        raise NotImplementedError("OCI adapter is not implemented yet.")


class LocalAdapter(LLMAdapter):
    async def create_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        raise NotImplementedError("Local adapter is not implemented yet.")

    async def stream_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Any:
        raise NotImplementedError("Local adapter is not implemented yet.")


_ADAPTERS: Dict[LLMProvider, LLMAdapter] = {}


def _infer_provider_from_model(model: Optional[str]) -> LLMProvider:
    default_provider = os.getenv("LLM_DEFAULT_PROVIDER", LLMProvider.OPENAI.value).lower()

    if model:
        lowered = model.lower()
        if lowered.startswith(("gpt", "o1", "o3", "o4")):
            return LLMProvider.OPENAI
        if lowered.startswith("gemini"):
            return LLMProvider.GEMINI
        if lowered.startswith("oci"):
            return LLMProvider.OCI
        if lowered.startswith(("local", "ollama", "llama", "qwen", "mistral")):
            return LLMProvider.LOCAL

    try:
        return LLMProvider(default_provider)
    except ValueError:
        return LLMProvider.OPENAI


def _normalize_provider(provider: Optional[str]) -> Optional[LLMProvider]:
    if not provider:
        return None

    lowered = provider.strip().lower()
    alias_map = {
        "openai": LLMProvider.OPENAI,
        "gpt": LLMProvider.OPENAI,
        "anthropic": LLMProvider.OPENAI,  # 현재 Anthropic 구현체 미지원, OpenAI로 fallback
        "gemini": LLMProvider.GEMINI,
        "google": LLMProvider.GEMINI,
        "oci": LLMProvider.OCI,
        "oracle": LLMProvider.OCI,
        "local": LLMProvider.LOCAL,
        "ollama": LLMProvider.LOCAL,
    }
    return alias_map.get(lowered)


def get_llm_adapter(
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> LLMAdapter:
    normalized_provider = _normalize_provider(provider)
    if normalized_provider is not None:
        provider_enum = normalized_provider
    else:
        provider_enum = _infer_provider_from_model(model)

    if provider_enum in _ADAPTERS:
        return _ADAPTERS[provider_enum]

    if provider_enum == LLMProvider.OPENAI:
        adapter: LLMAdapter = OpenAIAdapter()
    elif provider_enum == LLMProvider.GEMINI:
        adapter = GeminiAdapter()
    elif provider_enum == LLMProvider.OCI:
        adapter = OCIAdapter()
    else:
        adapter = LocalAdapter()

    _ADAPTERS[provider_enum] = adapter
    return adapter

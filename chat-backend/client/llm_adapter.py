import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI


class LLMProvider(str, Enum):
    OPENAI = "openai"


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


_adapter: Optional[OpenAIAdapter] = None


def get_llm_adapter(
    model: Optional[str] = None,
    provider: Optional[str] = None,
) -> LLMAdapter:
    """OpenAI 어댑터 반환 (제목 생성 등 단순 LLM 호출용)"""
    global _adapter
    if _adapter is None:
        _adapter = OpenAIAdapter()
    return _adapter

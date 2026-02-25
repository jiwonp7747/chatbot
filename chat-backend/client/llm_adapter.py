import os
import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
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


@dataclass
class _CompatDelta:
    content: Optional[str]


@dataclass
class _CompatMessage:
    content: str


@dataclass
class _CompatChoice:
    message: Optional[_CompatMessage] = None
    delta: Optional[_CompatDelta] = None


@dataclass
class _CompatResponse:
    choices: List[_CompatChoice]


class _CompatStream:
    def __init__(self, content: str, chunk_size: int = 64) -> None:
        self._chunks = [content[i: i + chunk_size] for i in range(0, len(content), chunk_size)] or [""]
        self._index = 0
        self._closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._closed or self._index >= len(self._chunks):
            raise StopAsyncIteration

        chunk_text = self._chunks[self._index]
        self._index += 1
        return _CompatResponse(choices=[_CompatChoice(delta=_CompatDelta(content=chunk_text))])

    async def aclose(self) -> None:
        self._closed = True


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
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key
        self._client = None
        self._types = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        from google import genai
        from google.genai import types
        self._types = types
        self._client = genai.Client(api_key=self._api_key or os.getenv("GOOGLE_API_KEY"))
        return self._client

    @staticmethod
    def _build_contents(messages: List[Dict[str, str]]):
        """OpenAI messages → Gemini contents + system_instruction 분리"""
        contents = []
        system_parts = []
        for m in messages:
            role = (m.get("role") or "").lower()
            text = m.get("content") or ""
            if role == "system":
                system_parts.append(text)
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": text}]})
            else:
                contents.append({"role": "user", "parts": [{"text": text}]})
        return system_parts, contents

    async def create_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        client = self._get_client()
        system_parts, contents = self._build_contents(messages)
        config = self._types.GenerateContentConfig(
            system_instruction="\n".join(system_parts) if system_parts else None,
        )
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=contents,
            config=config,
        )
        return _CompatResponse(
            choices=[_CompatChoice(message=_CompatMessage(content=response.text))]
        )

    async def stream_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Any:
        client = self._get_client()
        system_parts, contents = self._build_contents(messages)
        config = self._types.GenerateContentConfig(
            system_instruction="\n".join(system_parts) if system_parts else None,
        )
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=contents,
            config=config,
        )
        return _CompatStream(content=response.text)


class OCIAdapter(LLMAdapter):
    def __init__(self) -> None:
        self._client = None
        self._oci = None

    def _get_client(self):
        if self._client is not None and self._oci is not None:
            return self._client, self._oci

        try:
            import oci
        except Exception as exc:
            raise RuntimeError(
                "OCI SDK가 설치되어 있지 않습니다. `pip install oci` 후 재시도하세요."
            ) from exc

        config_file = os.getenv("OCI_CONFIG_FILE", "~/.oci/config")
        config_profile = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
        expanded_config_file = os.path.expanduser(config_file)
        oci_config = oci.config.from_file(file_location=expanded_config_file, profile_name=config_profile)

        kwargs: Dict[str, Any] = {}
        service_endpoint = os.getenv("OCI_GENAI_ENDPOINT")
        if service_endpoint:
            kwargs["service_endpoint"] = service_endpoint

        self._client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=oci_config,
            **kwargs,
        )
        self._oci = oci
        return self._client, self._oci

    @staticmethod
    def _resolve_compartment_id(oci_config: Dict[str, Any]) -> str:
        return (
            os.getenv("OCI_COMPARTMENT_ID")
            or oci_config.get("compartment_id")
            or oci_config.get("tenancy")
            or ""
        )

    @staticmethod
    def _to_oci_messages(oci: Any, messages: List[Dict[str, str]]) -> List[Any]:
        oci_messages = []
        role_map = {
            "system": "SYSTEM",
            "user": "USER",
            "assistant": "ASSISTANT",
        }
        for m in messages:
            role = role_map.get((m.get("role") or "").lower(), "USER")
            text = m.get("content") or ""
            oci_messages.append(
                oci.generative_ai_inference.models.Message(
                    role=role,
                    content=[oci.generative_ai_inference.models.TextContent(text=text)],
                )
            )
        return oci_messages

    @staticmethod
    def _to_cohere_chat_payload(oci: Any, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        # Cohere 요청은 최종 사용자 메시지를 message로, 이전 대화는 chat_history로 전달
        if not messages:
            return {"message": "", "chat_history": []}

        normalized = [{"role": (m.get("role") or "").lower(), "content": (m.get("content") or "")} for m in messages]

        latest_user_index = -1
        for idx in range(len(normalized) - 1, -1, -1):
            if normalized[idx]["role"] == "user":
                latest_user_index = idx
                break

        if latest_user_index == -1:
            latest_user_index = len(normalized) - 1

        latest_message = normalized[latest_user_index]["content"]
        history_items = normalized[:latest_user_index]

        cohere_history: List[Any] = []
        for item in history_items:
            role = item["role"]
            content = item["content"]
            if role == "system":
                cohere_history.append(
                    oci.generative_ai_inference.models.CohereSystemMessage(message=content)
                )
            elif role == "assistant":
                cohere_history.append(
                    oci.generative_ai_inference.models.CohereChatBotMessage(message=content)
                )
            else:
                cohere_history.append(
                    oci.generative_ai_inference.models.CohereUserMessage(message=content)
                )

        return {"message": latest_message, "chat_history": cohere_history}

    @staticmethod
    def _api_format_for_model(model: str) -> str:
        lowered = (model or "").lower()
        if lowered.startswith("cohere."):
            return "COHERE"
        return "GENERIC"

    @staticmethod
    def _resolve_model_id(model: str) -> str:
        env_model_id = os.getenv("OCI_MODEL_ID", "").strip()
        if env_model_id and not model.startswith("ocid1."):
            return env_model_id
        return model

    @staticmethod
    def _extract_text(response_data: Any) -> str:
        if response_data is None:
            return ""

        chat_response = getattr(response_data, "chat_response", None) or response_data
        choices = getattr(chat_response, "choices", None) or []
        if choices:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message is not None:
                content = getattr(message, "content", None)
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts: List[str] = []
                    for item in content:
                        text = getattr(item, "text", None)
                        if isinstance(text, str):
                            parts.append(text)
                    if parts:
                        return "".join(parts)
                message_text = getattr(message, "message", None)
                if isinstance(message_text, str):
                    return message_text

        top_text = getattr(chat_response, "text", None)
        if isinstance(top_text, str):
            return top_text
        return str(chat_response)

    async def _call_chat(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        is_stream: bool,
    ) -> str:
        client, oci = self._get_client()
        oci_config = client.base_client.config
        compartment_id = self._resolve_compartment_id(oci_config)
        if not compartment_id:
            raise RuntimeError(
                "OCI compartment_id를 찾을 수 없습니다. OCI_COMPARTMENT_ID 환경변수 또는 ~/.oci/config를 확인하세요."
            )

        def _sync_call() -> str:
            api_format = self._api_format_for_model(model)
            if api_format == "COHERE":
                cohere_payload = self._to_cohere_chat_payload(oci, messages)
                chat_request = oci.generative_ai_inference.models.CohereChatRequest(
                    api_format="COHERE",
                    message=cohere_payload["message"],
                    chat_history=cohere_payload["chat_history"],
                    is_stream=is_stream,
                )
            else:
                oci_messages = self._to_oci_messages(oci, messages)
                chat_request = oci.generative_ai_inference.models.GenericChatRequest(
                    api_format=api_format,
                    messages=oci_messages,
                    is_stream=is_stream,
                )
            resolved_model_id = self._resolve_model_id(model)
            details = oci.generative_ai_inference.models.ChatDetails(
                compartment_id=compartment_id,
                serving_mode=oci.generative_ai_inference.models.OnDemandServingMode(
                    model_id=resolved_model_id
                ),
                chat_request=chat_request,
            )
            try:
                response = client.chat(chat_details=details)
            except Exception as exc:
                message = str(exc)
                if "Entity with key" in message and "not found" in message:
                    raise RuntimeError(
                        "OCI 모델 ID를 찾을 수 없습니다. DB model_type.api_model 값을 유효한 모델 OCID로 변경하거나 OCI_MODEL_ID를 설정하세요."
                    ) from exc
                raise
            return self._extract_text(response.data)

        return await asyncio.to_thread(_sync_call)

    async def create_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Any:
        content = await self._call_chat(
            model=model,
            messages=messages,
            is_stream=False,
        )
        return _CompatResponse(
            choices=[_CompatChoice(message=_CompatMessage(content=content))]
        )

    async def stream_completion(
        self,
        *,
        model: str,
        messages: List[Dict[str, str]],
    ) -> Any:
        content = await self._call_chat(
            model=model,
            messages=messages,
            is_stream=False,
        )
        return _CompatStream(content=content)


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
        "google_genai": LLMProvider.GEMINI,
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

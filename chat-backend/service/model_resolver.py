import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ModelType

logger = logging.getLogger("chat-server")


# DB provider 값 → LangChain init_chat_model prefix
_LANGCHAIN_PROVIDER_MAP = {
    "openai": "openai",
    "gemini": "google_genai",
    "oci": "oci",
    "local": "ollama",
    "openrouter": "openai",  # OpenAI-compatible
}


@dataclass
class ResolvedModel:
    model_key: str        # DB canonical key, e.g. "gpt-4.1"
    api_model: str        # SDK model name, e.g. "gpt-4.1"
    provider: str         # "OPENAI", "GEMINI", "OPENROUTER" 등
    model_string: str     # LangChain 포맷 "openai:gpt-4.1"
    model_kwargs: dict = field(default_factory=dict)  # 추가 kwargs {"base_url": ..., "api_key": ...}


DEFAULT_MODEL_KEY = os.getenv("DEFAULT_MODEL_KEY", "gpt-5.1-mini")
DEFAULT_PROVIDER = os.getenv("LLM_DEFAULT_PROVIDER", "OPENAI")


def _build_model_string(provider: str, api_model: str) -> str:
    """provider + api_model → LangChain model string"""
    lc_provider = _LANGCHAIN_PROVIDER_MAP.get(provider.lower(), provider.lower())
    return f"{lc_provider}:{api_model}"


def _build_model_kwargs(provider: str) -> dict:
    """provider별 추가 kwargs (base_url, api_key 등)"""
    if provider.upper() == "OPENROUTER":
        return {
            "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        }
    return {}


def _infer_provider_from_model_name(model_name: str) -> str:
    lowered = (model_name or "").lower()
    if lowered.startswith(("gpt", "o1", "o3", "o4")):
        return "OPENAI"
    if lowered.startswith("gemini"):
        return "GEMINI"
    if lowered.startswith("oci"):
        return "OCI"
    if lowered.startswith(("local", "ollama", "llama", "qwen", "mistral")):
        return "LOCAL"
    # OpenRouter 모델은 "org/model" 형태 (e.g. "anthropic/claude-sonnet-4")
    if "/" in lowered:
        return "OPENROUTER"
    return DEFAULT_PROVIDER


async def _find_model_by_key_or_api_model(
    db: AsyncSession,
    requested_model: str,
) -> Optional[ModelType]:
    query = select(ModelType).where(
        (ModelType.model_type == requested_model) | (ModelType.api_model == requested_model)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def _find_default_model(db: AsyncSession) -> Optional[ModelType]:
    default_query = select(ModelType).where(
        ModelType.is_active.is_(True),
        ModelType.model_type == DEFAULT_MODEL_KEY,
    )
    default_result = await db.execute(default_query)
    default_model = default_result.scalar_one_or_none()
    if default_model:
        return default_model

    fallback_query = select(ModelType).where(ModelType.is_active.is_(True)).limit(1)
    fallback_result = await db.execute(fallback_query)
    return fallback_result.scalar_one_or_none()


async def resolve_model_config(
    db: AsyncSession,
    requested_model: Optional[str],
) -> ResolvedModel:
    """
    모델 라우팅 정보를 DB model_type 테이블 기준으로 해석하고,
    최종 LangChain model_string과 model_kwargs까지 생성합니다.
    """
    request_model = requested_model or DEFAULT_MODEL_KEY
    db_model = await _find_model_by_key_or_api_model(db, request_model)

    if db_model and (db_model.is_active is False):
        logger.warning("요청 모델이 비활성화 상태입니다: %s", request_model)
        db_model = None

    if db_model is None:
        logger.warning("요청 모델을 DB에서 찾지 못해 기본 모델로 대체합니다: %s", request_model)
        db_model = await _find_default_model(db)

    if db_model is None:
        provider = _infer_provider_from_model_name(request_model)
        return ResolvedModel(
            model_key=request_model,
            api_model=request_model,
            provider=provider,
            model_string=_build_model_string(provider, request_model),
            model_kwargs=_build_model_kwargs(provider),
        )

    provider = db_model.provider or _infer_provider_from_model_name(db_model.model_type or "")
    api_model = db_model.api_model or db_model.model_type
    model_key = db_model.model_type or api_model

    return ResolvedModel(
        model_key=model_key,
        api_model=api_model,
        provider=provider,
        model_string=_build_model_string(provider, api_model),
        model_kwargs=_build_model_kwargs(provider),
    )

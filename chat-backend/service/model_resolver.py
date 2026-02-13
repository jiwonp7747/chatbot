import logging
import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ModelType

logger = logging.getLogger("chat-server")


@dataclass
class ResolvedModel:
    request_model: str
    model_key: str
    api_model: str
    provider: str


DEFAULT_MODEL_KEY = os.getenv("DEFAULT_MODEL_KEY", "gpt-5.1-mini")
DEFAULT_PROVIDER = os.getenv("LLM_DEFAULT_PROVIDER", "OPENAI")


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
    모델 라우팅 정보(provider, api_model)를 DB model_type 테이블 기준으로 해석합니다.
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
            request_model=request_model,
            model_key=request_model,
            api_model=request_model,
            provider=provider,
        )

    provider = db_model.provider or _infer_provider_from_model_name(db_model.model_type or "")
    api_model = db_model.api_model or db_model.model_type
    model_key = db_model.model_type or api_model

    return ResolvedModel(
        request_model=request_model,
        model_key=model_key,
        api_model=api_model,
        provider=provider,
    )

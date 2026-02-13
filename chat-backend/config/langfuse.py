"""Langfuse OpenTelemetry 기반 트레이싱 설정

Python 3.14 + Pydantic V1 호환성 문제로 Langfuse SDK 대신
OpenTelemetry 프로토콜을 사용하여 Langfuse에 트레이스를 전송합니다.
"""
import base64
import os
import logging

logger = logging.getLogger("chat-server")

_initialized = False


def init_langfuse_tracing() -> bool:
    """Langfuse OTEL 트레이싱 초기화. 서버 시작 시 1회 호출"""
    global _initialized
    if _initialized:
        return True

    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "") or os.getenv("LANGFUSE_BASE_URL", "")

    if not all([secret_key, public_key, host]):
        logger.info("ℹ️ Langfuse 설정 없음 — 트레이싱 비활성화")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.langchain import LangchainInstrumentor

        # 인증 헤더 구성
        auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()

        # OTEL TracerProvider 설정
        resource = Resource.create({"service.name": "chat-backend"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=f"{host}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {auth}"}
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # LangChain/LangGraph 자동 계측
        LangchainInstrumentor().instrument()

        _initialized = True
        logger.info(f"✅ Langfuse OTEL 트레이싱 활성화: {host}")
        return True

    except Exception as e:
        logger.warning(f"⚠️ Langfuse OTEL 초기화 실패: {e}")
        return False

"""OpenTelemetry 트레이싱 설정

OTEL Collector를 통해 분산 트레이싱을 수행합니다.
LangchainInstrumentor로 LangChain/LangGraph 호출을 자동 계측하고,
get_tracer() / trace_tool()로 수동 span 생성도 지원합니다.

환경변수:
    OTEL_ENABLED: 텔레메트리 활성화 여부 (true/false)
    OTEL_SERVICE_NAME: 서비스 이름 (기본값: chat-backend)
    OTEL_COLLECTOR_BASE_URL: OTEL Collector 엔드포인트 (예: http://host:30318)
"""
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger("chat-server")

_initialized = False

# 환경변수
OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").lower() in ("true", "1", "yes")
OTEL_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "chat-backend")
OTEL_COLLECTOR_BASE_URL = os.getenv("OTEL_COLLECTOR_BASE_URL", "")


def init_telemetry() -> bool:
    """OTEL 트레이싱 초기화. 서버 시작 시 1회 호출."""
    global _initialized
    if _initialized:
        return True

    if not OTEL_ENABLED:
        logger.info("ℹ️ OTEL_ENABLED=false — 트레이싱 비활성화")
        return False

    if not OTEL_COLLECTOR_BASE_URL:
        logger.warning("⚠️ OTEL_COLLECTOR_BASE_URL 미설정 — 트레이싱 비활성화")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=f"{OTEL_COLLECTOR_BASE_URL}/v1/traces"
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # LangChain/LangGraph 자동 계측
        try:
            from opentelemetry.instrumentation.langchain import LangchainInstrumentor
            LangchainInstrumentor().instrument()
            logger.info("✅ LangChain 자동 계측 활성화")
        except ImportError:
            logger.warning("⚠️ opentelemetry-instrumentation-langchain 미설치")
        except Exception as e:
            logger.warning(f"⚠️ LangChain 계측 실패: {e}")

        _initialized = True
        logger.info(
            f"✅ OTEL 트레이싱 활성화: service={OTEL_SERVICE_NAME}, "
            f"endpoint={OTEL_COLLECTOR_BASE_URL}/v1/traces"
        )
        return True

    except Exception as e:
        logger.warning(f"⚠️ OTEL 초기화 실패: {e}")
        return False


def get_tracer(name: str = "chat-backend"):
    """OTEL tracer 반환. 미초기화 시 no-op tracer 반환."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return None


@contextmanager
def trace_tool(tool_name: str, attributes: dict | None = None):
    """도구 호출용 span 생성 컨텍스트 매니저. 미초기화 시 no-op."""
    if not _initialized:
        yield None
        return

    try:
        from opentelemetry import trace as _trace

        tracer = _trace.get_tracer("chat-backend")
        with tracer.start_as_current_span(tool_name) as span:
            if attributes:
                for k, v in attributes.items():
                    if v is not None:
                        span.set_attribute(
                            k, v if isinstance(v, (str, int, float, bool)) else str(v)
                        )
            yield span
    except Exception:
        yield None

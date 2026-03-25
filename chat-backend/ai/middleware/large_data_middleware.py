"""대용량 도구 결과 파일 저장 미들웨어

도구 실행 결과가 threshold를 초과하면 S3에 저장하고,
에이전트에게 파일 경로를 알려줍니다.
read_file 도구는 제공하지 않습니다 (무한 루프 방지).
"""
import logging
from typing import override, Callable, Awaitable

from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from deepagents.middleware.filesystem import FilesystemMiddleware

logger = logging.getLogger(__name__)


class LargeDataMiddleware(FilesystemMiddleware):
    """도구 결과가 threshold 초과 시 파일에 저장하는 미들웨어

    Args:
        backend: FilesystemBackend 인스턴스
        threshold: 파일 저장 기준 크기 (바이트, 기본 100KB)
    """

    def __init__(self, backend, threshold: int = 10000):
        super().__init__(backend=backend)
        self.threshold = threshold

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        result = handler(request)
        return self._process_tool_result(result, request)

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        result = await handler(request)
        processed = self._process_tool_result(result, request)
        if isinstance(processed, ToolMessage):
            logger.info(f"[LargeData] awrap_tool_call 리턴 시 response_metadata={processed.response_metadata}")
        return processed

    def _process_tool_result(
        self, result: ToolMessage | Command, request: ToolCallRequest
    ) -> ToolMessage | Command:
        """sync/async 공통 도구 결과 처리 로직"""
        tool_name = request.tool_call.get("name", "unknown")
        logger.info(f"[LargeData] 도구 결과 처리: tool={tool_name}, result_type={type(result).__name__}")

        if isinstance(result, ToolMessage):
            artifact = result.artifact
            response_metadata = dict(result.response_metadata) if result.response_metadata else {}

            if artifact is not None:
                artifact_str = str(artifact)
                artifact_size = len(artifact_str)
                logger.info(f"[LargeData] tool={tool_name}, type=artifact, size={artifact_size}bytes, threshold={self.threshold}")

                if artifact_size > self.threshold:
                    resolved = self._get_backend(request.runtime)
                    tool_call_id = request.tool_call["id"]
                    thread_id = request.runtime.config["configurable"]["thread_id"]
                    output_path = f"/data/{thread_id}/{tool_name}_{tool_call_id}.jsonl"

                    resolved.write(output_path, artifact_str)
                    logger.info(f"[LargeData] S3 저장 완료: tool={tool_name}, path={output_path}, size={artifact_size}bytes")

                    response_metadata["data_ref_type"] = "file"
                    response_metadata["file_path"] = output_path
                    updated = result.model_copy(update={
                        "artifact": None,
                        "response_metadata": response_metadata,
                        "content": (
                            f"`{tool_name}` 도구의 실행 결과가 너무 크기 때문에 "
                            f"`{output_path}`에 저장했습니다. "
                            "저장된 데이터를 기반으로 작업을 계속하세요."
                        ),
                    })
                    logger.info(f"[LargeData] model_copy 후 response_metadata={updated.response_metadata}")
                    return updated
                else:
                    logger.info(f"[LargeData] 인라인 유지: tool={tool_name}, size={artifact_size}bytes (threshold 미만)")
                    response_metadata["data_ref_type"] = "artifact"
                    return result.model_copy(update={
                        "response_metadata": response_metadata,
                    })
            else:
                content_str = str(result.content)
                content_size = len(content_str)
                logger.info(f"[LargeData] tool={tool_name}, type=content, size={content_size}bytes, threshold={self.threshold}")
                if content_size > self.threshold:
                    resolved = self._get_backend(request.runtime)
                    tool_call_id = request.tool_call["id"]
                    thread_id = request.runtime.config["configurable"]["thread_id"]
                    output_path = f"/data/{thread_id}/{tool_name}_{tool_call_id}.jsonl"

                    resolved.write(output_path, content_str)
                    logger.info(f"[LargeData] S3 저장 완료: tool={tool_name}, path={output_path}, size={content_size}bytes")

                    response_metadata["data_ref_type"] = "file"
                    response_metadata["file_path"] = output_path
                    return result.model_copy(update={
                        "response_metadata": response_metadata,
                        "content": (
                            f"`{tool_name}` 도구의 실행 결과가 너무 크기 때문에 "
                            f"`{output_path}`에 저장했습니다. "
                            "저장된 데이터를 기반으로 작업을 계속하세요."
                        ),
                    })

        return result

    @override
    def wrap_model_call(self, request, handler):
        # FilesystemMiddleware.wrap_model_call을 건너뛰어 read_file/grep 도구 프롬프트 비활성화
        # (read_file 호출 → 파일 생성 → read_file 호출 무한 루프 방지)
        return handler(request)


def create_large_data_middleware(backend, threshold: int = 10000) -> LargeDataMiddleware:
    """LargeDataMiddleware 팩토리 함수

    서브에이전트의 middleware 리스트에 추가하여 사용합니다.

    Args:
        backend: get_filesystem_backend()로 생성한 FilesystemBackend
        threshold: 파일 저장 기준 크기 (바이트)
    """
    return LargeDataMiddleware(backend=backend, threshold=threshold)

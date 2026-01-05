import uvicorn
import base64
import logging
from typing import List, Optional, Literal
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

# 로거 설정
logger = logging.getLogger(__name__)

class YieldDataRow(BaseModel):
    workDate: str = Field(..., description="YYYY-MM-DD format")
    yieldRate: Optional[float] = Field(None, description="Yield % (PIPE only)")
    finalYield: Optional[float] = Field(None, description="Final Yield % (BAR only)")
    prodQty: float = Field(..., description="Production Quantity")
    inputQty: Optional[float] = Field(None, description="Input Quantity")

class ChartRequest(BaseModel):
    type: Literal["PIPE", "BAR"]
    data: List[YieldDataRow]

MCP_SERVER_SSE_URL = "http://localhost:3000/sse"

router = APIRouter(prefix="/test", tags=["test"])


@router.post("/get-chart")
async def get_chart(request: ChartRequest):
    logger.info("차트 생성 요청 시작", extra={
        "chart_type": request.type,
        "data_count": len(request.data)
    })

    try:
        # SSE 클라이언트 연결 시도
        logger.debug("MCP 서버 SSE 연결 시도", extra={"url": MCP_SERVER_SSE_URL})

        async with sse_client(MCP_SERVER_SSE_URL) as (read, write):
            logger.debug("SSE 클라이언트 연결 성공", extra={
                "read_stream_type": type(read).__name__,
                "write_stream_type": type(write).__name__
            })

            async with ClientSession(read, write) as session:
                logger.debug("ClientSession 생성 완료")

                # 1. 초기화 타임아웃 방지를 위해 명시적 초기화
                logger.debug("세션 초기화 시작")
                await session.initialize()
                logger.info("세션 초기화 완료")

                # 2. 도구 목록 확인
                logger.debug("사용 가능한 도구 목록 조회 중")
                available_tools = await session.list_tools()
                tool_names = [t.name for t in available_tools.tools]
                logger.info("사용 가능한 도구 목록", extra={"tools": tool_names})

                if "generate_yield_chart" not in tool_names:
                    logger.error("필수 도구를 찾을 수 없음", extra={
                        "required_tool": "generate_yield_chart",
                        "available_tools": tool_names
                    })
                    raise HTTPException(status_code=400, detail="도구를 찾을 수 없습니다.")

                # 3. 도구 실행
                logger.debug("차트 생성 도구 호출 시작", extra={
                    "tool": "generate_yield_chart",
                    "arguments": request.model_dump()
                })
                result = await session.call_tool(
                    "generate_yield_chart",
                    arguments=request.model_dump()
                )
                logger.debug("차트 생성 도구 호출 완료", extra={
                    "result_type": type(result).__name__,
                    "content_count": len(result.content) if hasattr(result, 'content') else 0
                })

                # 4. MCP 서버 자체 에러 체크
                if getattr(result, 'isError', False):
                    logger.error("MCP 서버에서 에러 반환", extra={
                        "error_content": str(result.content)
                    })
                    raise Exception(f"MCP Server Error: {result.content}")

                # 5. 결과 파싱 (이미지 추출)
                logger.debug("결과에서 이미지 데이터 추출 중")
                image_data = None

                for idx, content in enumerate(result.content):
                    logger.debug(f"Content {idx} 확인", extra={
                        "content_type": content.type,
                        "has_data": hasattr(content, 'data')
                    })
                    if content.type == "image":
                        image_data = content.data
                        logger.info("이미지 데이터 발견", extra={
                            "data_length": len(image_data) if image_data else 0
                        })
                        break

                if not image_data:
                    error_text = next((c.text for c in result.content if c.type == "text"), "Unknown Error")
                    logger.error("이미지 데이터를 찾을 수 없음", extra={
                        "error_text": error_text,
                        "content_types": [c.type for c in result.content]
                    })
                    raise HTTPException(status_code=500, detail=f"No image returned: {error_text}")

                # Base64 디코딩
                logger.debug("Base64 이미지 디코딩 시작")
                image_binary = base64.b64decode(image_data)
                logger.info("차트 생성 완료", extra={
                    "image_size_bytes": len(image_binary)
                })

                return Response(content=image_binary, media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("차트 생성 중 예외 발생", extra={
            "error_type": type(e).__name__,
            "error_message": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
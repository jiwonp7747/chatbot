"""
LangGraph 채팅 엔드포인트 테스트 스크립트

사용법:
    python test_langgraph.py
"""
import asyncio
import httpx
import json


async def test_langgraph_chat():
    """LangGraph 기반 채팅 엔드포인트 테스트"""

    url = "http://localhost:8000/chat/stream-chat-graph"

    # 테스트 요청 데이터
    request_data = {
        "chat_session_id": 1,
        "prompt": "안녕하세요! LangGraph 테스트입니다.",
        "model": "gpt-5.1-mini"
    }

    print("=" * 60)
    print("LangGraph 채팅 엔드포인트 테스트")
    print("=" * 60)
    print(f"\n📤 요청:")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    print(f"\n📡 URL: {url}")
    print("\n" + "=" * 60)
    print("📥 응답 (스트리밍):\n")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                url,
                json=request_data
            ) as response:
                # 응답 상태 확인
                if response.status_code != 200:
                    print(f"❌ 에러: HTTP {response.status_code}")
                    print(await response.aread())
                    return

                # SSE 스트림 처리
                full_content = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # "data: " 제거

                        try:
                            data = json.loads(data_str)
                            status = data.get("status")
                            content = data.get("content", "")
                            error = data.get("error")

                            if error:
                                print(f"\n❌ 에러: {error}")
                                break

                            if status == "streaming" and content:
                                print(content, end="", flush=True)
                                full_content += content

                            elif status == "done":
                                print("\n\n" + "=" * 60)
                                print("✅ 스트리밍 완료")
                                print("=" * 60)
                                print(f"\n전체 응답 길이: {len(full_content)} 자")
                                break

                        except json.JSONDecodeError:
                            print(f"\n⚠️ JSON 파싱 실패: {data_str}")

    except httpx.ConnectError:
        print("❌ 서버 연결 실패")
        print("서버가 실행 중인지 확인하세요: python main.py")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")


async def test_legacy_chat():
    """레거시 채팅 엔드포인트 테스트 (비교용)"""

    url = "http://localhost:8000/chat/stream-chat"

    request_data = {
        "chat_session_id": 1,
        "prompt": "안녕하세요! 레거시 테스트입니다.",
        "model": "gpt-5.1-mini"
    }

    print("\n\n" + "=" * 60)
    print("레거시 채팅 엔드포인트 테스트 (비교)")
    print("=" * 60)
    print(f"\n📤 요청:")
    print(json.dumps(request_data, indent=2, ensure_ascii=False))
    print(f"\n📡 URL: {url}")
    print("\n" + "=" * 60)
    print("📥 응답 (스트리밍):\n")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                url,
                json=request_data
            ) as response:
                if response.status_code != 200:
                    print(f"❌ 에러: HTTP {response.status_code}")
                    return

                full_content = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                            status = data.get("status")
                            content = data.get("content", "")

                            if status == "streaming" and content:
                                print(content, end="", flush=True)
                                full_content += content

                            elif status == "done":
                                print("\n\n" + "=" * 60)
                                print("✅ 스트리밍 완료")
                                print("=" * 60)
                                print(f"\n전체 응답 길이: {len(full_content)} 자")
                                break

                        except json.JSONDecodeError:
                            pass

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")


async def compare_endpoints():
    """두 엔드포인트 비교 테스트"""
    print("\n" + "🔬" * 30)
    print("LangGraph vs 레거시 엔드포인트 비교 테스트")
    print("🔬" * 30 + "\n")

    # LangGraph 테스트
    await test_langgraph_chat()

    # 레거시 테스트
    await test_legacy_chat()

    print("\n\n" + "📊" * 30)
    print("테스트 완료!")
    print("📊" * 30)


if __name__ == "__main__":
    # 기본 테스트: LangGraph만
    asyncio.run(test_langgraph_chat())

    # 비교 테스트를 원하면 아래 주석 해제
    # asyncio.run(compare_endpoints())

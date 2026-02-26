# AI 패키지 메시지 처리 아키텍처

사용자 메시지가 Supervisor(Main Agent)를 거쳐 Subagent 도구로 라우팅되는 흐름을 보여줍니다.

```mermaid
flowchart TD
    User(["👤 User"])

    User -->|"POST /chat/stream-chat-graph"| Router["chat_router.py<br/>StreamingResponse"]
    Router --> Service["chat_langgraph_service.py<br/>process_chat_with_langgraph()"]

    Service -->|"1. ChatGraphState 생성"| Orchestrator

    subgraph Orchestrator["🎯 Orchestrator (ai/graph/orchestrator.py)"]
        direction TB
        LoadHistory["load_chat_history_node<br/>최근 10개 대화 로드"]
        BuildAgent["_build_main_agent()<br/>Subagent 도구 등록"]
        LoadHistory --> BuildAgent
        BuildAgent --> MainAgent

        subgraph MainAgent["🧠 Supervisor — Main Agent (ReAct Loop)"]
            direction TB
            Intent{"의도 판단<br/>(MAIN_AGENT_PROMPT)"}
            Intent -->|"문서 검색 필요"| CallRAG["search_documents 호출"]
            Intent -->|"외부 도구 필요"| CallTool["execute_tools 호출"]
            Intent -->|"일반 대화"| DirectReply["직접 응답 생성"]
        end
    end

    CallRAG --> RAGAgent
    CallTool --> ToolAgent

    subgraph RAGAgent["📚 RagAgent (ai/agents/rag_agent.py)"]
        direction TB
        RAGLoop["ReAct Sub-Loop"]
        RAGLoop --> TagSearch["tag_search_tool<br/>태그 기반 검색"]
        RAGLoop --> SemanticSearch["semantic_search_tool<br/>의미 기반 검색"]
    end

    subgraph ToolAgent["🔧 ToolAgent (ai/agents/tool_agent.py)"]
        direction TB
        ToolLoop["ReAct Sub-Loop"]
        ToolLoop --> MCP1["EChart MCP<br/>(port 3100)"]
        ToolLoop --> MCP2["Memory MCP<br/>(port 6333)"]
        ToolLoop --> MCPn["기타 MCP 도구..."]
    end

    TagSearch -->|"HTTP POST"| VectorDB[("Agent Memory Server<br/>localhost:6333")]
    SemanticSearch -->|"HTTP POST"| VectorDB

    MCP1 -->|"SSE"| EChart["echart-mcp-server"]
    MCP2 -->|"Streamable HTTP"| MemoryServer["agent-memory-server"]

    RAGAgent -->|"검색 결과 반환"| MainAgent
    ToolAgent -->|"실행 결과 반환"| MainAgent

    MainAgent -->|"ai_response"| SSE["SSE 스트리밍<br/>(64byte 청크)"]
    DirectReply --> SSE
    SSE -->|"StreamStatus.STREAMING"| User

    classDef user fill:#6366F1,color:#fff,stroke:none,font-weight:bold
    classDef router fill:#1E293B,color:#E2E8F0,stroke:#334155
    classDef orchestrator fill:#0F172A,color:#E2E8F0,stroke:#6366F1,stroke-width:2px
    classDef supervisor fill:#4F46E5,color:#fff,stroke:none
    classDef subagent fill:#7C3AED,color:#fff,stroke:none
    classDef tool fill:#0EA5E9,color:#fff,stroke:none
    classDef external fill:#059669,color:#fff,stroke:none
    classDef stream fill:#F59E0B,color:#1E293B,stroke:none,font-weight:bold
    classDef decision fill:#EC4899,color:#fff,stroke:none

    class User user
    class Router,Service router
    class MainAgent supervisor
    class RAGAgent,ToolAgent subagent
    class TagSearch,SemanticSearch,MCP1,MCP2,MCPn tool
    class VectorDB,EChart,MemoryServer external
    class SSE stream
    class Intent decision
```

## 핵심 구조: 2단계 ReAct 에이전트 계층

| 계층 | 구성 요소 | 역할 |
|------|-----------|------|
| **Level 1** | Supervisor (Main Agent) | 사용자 의도 판단 → 적절한 Subagent 도구 호출 |
| **Level 2** | RagAgent / ToolAgent | 각각 독립된 ReAct 루프로 실제 작업 수행 |

## Subagent 도구 등록 흐름

```mermaid
flowchart LR
    subgraph Startup["서버 시작 (main.py lifespan)"]
        MCPInit["MCPRegistry.initialize()"]
    end

    subgraph BuildPhase["_build_main_agent()"]
        direction TB
        Wrap["wrap_mcp_tools()<br/>MCP → StructuredTool 변환"]
        RAG["RagAgent(model).as_tool()<br/>→ search_documents"]
        Tool["ToolAgent(model, mcp_tools).as_tool()<br/>→ execute_tools"]
        Create["create_agent(model,<br/>tools=[search_documents, execute_tools],<br/>system_prompt=MAIN_AGENT_PROMPT)"]

        Wrap --> Tool
        RAG --> Create
        Tool --> Create
    end

    MCPInit -->|"MCP 도구 목록"| Wrap
    Create --> Agent(["Compiled ReAct Graph<br/>(Main Agent)"])

    classDef phase fill:#1E293B,color:#E2E8F0,stroke:#334155
    classDef step fill:#4F46E5,color:#fff,stroke:none
    classDef result fill:#059669,color:#fff,stroke:none,font-weight:bold

    class Wrap,RAG,Tool step
    class Create step
    class Agent result
```

## 요약

- **BaseAgent** ABC를 상속하여 `as_tool()`로 LangChain `@tool` 데코레이터를 씌우면, 완전한 ReAct 에이전트가 하나의 도구로 등록됨
- Main Agent는 `search_documents`, `execute_tools` 2개의 메타 도구만 인식
- 각 메타 도구 내부에서 실제 세부 도구(RAG 검색, MCP 호출)가 실행됨

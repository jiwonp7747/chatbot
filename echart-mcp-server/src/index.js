import './tracing.js';  // Must be FIRST — initializes OTEL before other imports
import express from 'express';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { mcpServer } from './mcp-server.js';
import { extractContext, withSpan } from './tracing.js';

const app = express();
const PORT = 3100;

app.use(express.json());

const transports = new Map();
const sessionContexts = new Map();  // sessionId → OTEL Context

app.get('/sse', async (req, res) => {
    console.log(`[SSE] 🔗 New connection request from: ${req.ip}`);

    // traceparent 헤더에서 트레이스 컨텍스트 추출
    const parentCtx = extractContext(req.headers);

    const transport = new SSEServerTransport('/messages', res);
    await mcpServer.connect(transport);

    const sessionId = transport.sessionId;
    transports.set(sessionId, transport);
    sessionContexts.set(sessionId, parentCtx);  // 세션별 트레이스 컨텍스트 저장

    console.log(`✅ Session Created: ${sessionId}`);
    console.log("[SSE] ✅ Connected and waiting for messages...");

    req.on('close', () => {
        console.log(`❌ Session Closed: ${sessionId}`);
        transports.delete(sessionId);
        sessionContexts.delete(sessionId);  // 컨텍스트도 정리
    });
});

app.post('/messages', async (req, res) => {
    const sessionId = req.query.sessionId;

    if (!sessionId) {
        return res.status(400).send("Missing sessionId query parameter");
    }
    console.log(`[MSG] 📥 Incoming message for session: ${sessionId}`);

    const transport = transports.get(sessionId);
    if (!transport) {
        console.error("[MSG] ❌ No active transport found. SSE connection might be closed.");
        return res.status(404).send("Session not found");
    }

    // 세션의 부모 트레이스 컨텍스트로 span 생성
    const parentCtx = sessionContexts.get(sessionId);

    try {
        await withSpan('mcp.handle_message', parentCtx, { 'mcp.session_id': sessionId }, async () => {
            await transport.handleMessage(req.body);
        });
        res.status(202).json({ status: 'accepted' });
        console.log("[MSG] ✅ Message handled successfully");
    } catch (error) {
        console.error("[MSG] ❌ Error handling message:", error);
        res.status(500).json({ error: error.message });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 MCP Server is running on http://localhost:${PORT}`);
    console.log(`👉 SSE Endpoint: http://localhost:${PORT}/sse`);
});
import express from 'express';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import { mcpServer } from './mcp-server.js'; // 확장자 .js 필수

const app = express();
const PORT = 3000;

app.use(express.json());

const transports = new Map();

app.get('/sse', async (req, res) => {
    console.log(`[SSE] 🔗 New connection request from: ${req.ip}`);

    const transport = new SSEServerTransport('/messages', res);

    // MCP 서버 연결
    await mcpServer.connect(transport);

    // 세션 ID 확인 및 저장
    const sessionId = transport.sessionId;
    transports.set(sessionId, transport);

    console.log(`✅ Session Created: ${sessionId}`);
    console.log("[SSE] ✅ Connected and waiting for messages...");

    // 연결 종료 시 Map에서 제거
    req.on('close', () => {
        console.log(`❌ Session Closed: ${sessionId}`);
        transports.delete(sessionId);
    });
});

app.post('/messages', async (req, res) => {
    const sessionId = req.query.sessionId;

    // 1. 세션 ID 확인
    if (!sessionId) {
        return res.status(400).send("Missing sessionId query parameter");
    }
    console.log(`[MSG] 📥 Incoming message for session: ${req.query.sessionId}`);

    // 2. Transport 찾기
    const transport = transports.get(sessionId);
    if (!transport) {
        console.error("[MSG] ❌ No active transport found. SSE connection might be closed.");
        return res.status(404).send("Session not found");
    }

    try {
        await transport.handleMessage(req.body);
        res.status(202).json({ status: 'accepted' });
        console.log("[MSG] ✅ Message handled successfully");
    } catch (error) {
        console.error("[MSG] ❌ Error handling message:", error);
        // ZodError 등 내부 로직 에러 처리
        res.status(500).json({ error: error.message });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 MCP Server is running on http://localhost:${PORT}`);
    console.log(`👉 SSE Endpoint: http://localhost:${PORT}/sse`);
});
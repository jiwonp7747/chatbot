import axios from 'axios';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { createYieldChart } from './chart-engine.js';
import {handleGenerateYieldChart, handleDetailLookup, handleFetchYieldHistory} from "./handlers.js";

// MCP 서버 인스턴스 생성
const mcpServer = new McpServer({
    name: "Yield-Chart-Server",
    version: "1.0.0"
});

// 1. generate_yield_chart
mcpServer.registerTool(
    "generate_yield_chart",
    {
        description: "입력된 생산 이력 데이터를 바탕으로 수율 시각화 차트 데이터를 생성합니다.",
        inputSchema: z.object({
            type: z.enum(["PIPE", "BAR"]).describe("품목 타입 (PIPE 또는 BAR)"),
            data: z.array(z.object({
                workDate: z.string().describe("작업 일자 (YYYY-MM-DD format)"),
                yieldRate: z.number().optional().describe("수율 % (PIPE 전용)"),
                finalYield: z.number().optional().describe("최종 수율 % (BAR 전용)"),
                prodQty: z.number().describe("생산 수량"),
                inputQty: z.number().optional().describe("투입 수량")
            })).describe("생산 이력 로우 데이터 리스트")
        })
    },
    handleGenerateYieldChart
);

// 2. get_yield_history
mcpServer.registerTool(
    "get_yield_history",
    {
        description: "PIPE 또는 BAR의 과거 생산 이력 및 수율 데이터를 조회합니다. 다양한 검색 조건을 조합하여 데이터를 리스트 형태로 반환합니다.",
        inputSchema: z.object({
            token: z.string().describe("Backend API 인증을 위한 Bearer Access Token"),
            itemType: z.string().describe("품목 타입 (예: PIPE, BAR)"),
            steelGradeL: z.string().describe("강종 대분류"),
            steelGradeGroup: z.string().describe("강종 그룹"),
            shape: z.string().describe("형상"),
            inhouseSteelName: z.string().describe("사내 강종명"),
            orderHeatTreat: z.string().describe("주문 열처리"),
            materialL: z.string().describe("소재 대분류"),
            surface: z.string().describe("표면 상태"),
            orderOuterDia: z.number().describe("주문 외경 (BigDecimal)")
        })
    },
    handleFetchYieldHistory
);

// 3. get_bar_yield_detail
mcpServer.registerTool(
    "get_bar_yield_detail",
    {
        description: "특정 BAR 제품의 Lot No를 기반으로 상세 수율 정보 및 생산 이력을 조회합니다.",
        inputSchema: z.object({
            token: z.string().describe("Backend API 인증을 위한 Bearer Access Token"),
            barId: z.string().describe("조회할 BAR의 Lot No (ID)")
        })
    },
    ({ token, barId }) => handleDetailLookup("BAR", barId, token)
);

// 4. get_pipe_yield_detail
mcpServer.registerTool(
    "get_pipe_yield_detail",
    {
        description: "특정 PIPE 제품의 Lot No를 기반으로 상세 수율 정보 및 생산 이력을 조회합니다.",
        inputSchema: z.object({
            token: z.string().describe("Backend API 인증을 위한 Bearer Access Token"),
            pipeId: z.string().describe("조회할 PIPE의 Lot No (ID)")
        })
    },
    ({ token, pipeId }) => handleDetailLookup("PIPE", pipeId, token)
);

export { mcpServer };
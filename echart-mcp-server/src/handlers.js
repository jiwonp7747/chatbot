import axios from 'axios';
import { createYieldChart } from "./chart-engine.js";
import { withSpan } from './tracing.js';

/** 1. 차트 생성 핸들러 */
const handleGenerateYieldChart = async ({ type, data }) => {
    return withSpan('tool.generate_yield_chart', null, {
        'tool.name': 'generate_yield_chart',
        'tool.type': type,
        'tool.data_rows': data.length
    }, async (span) => {
        try {
            console.log(`[MCP] Request received. Type: ${type}, Rows: ${data.length}`);
            const result = await createYieldChart(type, data);
            span.setAttribute('tool.chart_count', result.count);
            return {
                content: [
                    { type: "text", text: `성공적으로 ${result.count}개월 치 데이터에 대한 차트를 생성했습니다.` },
                    { type: "image", data: result.base64Image, mimeType: "image/png" }
                ]
            };
        } catch (error) {
            console.error("[MCP Error]", error);
            return { content: [{ type: "text", text: `차트 생성 실패: ${error.message}` }], isError: true };
        }
    });
};

/** 2. 수율 히스토리 조회 핸들러 */
const handleFetchYieldHistory = async (args) => {
    const { token, ...searchParams } = args;
    return withSpan('tool.get_yield_history', null, {
        'tool.name': 'get_yield_history',
        'tool.item_type': searchParams.itemType
    }, async (span) => {
        try {
            console.log(`[MCP] History 조회 요청, Params:`, searchParams);
            const response = await axios.post(
                'http://localhost:8481/seed/api/yield/history',
                searchParams,
                { headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } }
            );

            console.log(`[MCP] 수율 이력 조회 결과: ${JSON.stringify(response.data, null, 2)}`);
            const historyList = response.data;
            span.setAttribute('tool.result_count', historyList.length);
            return {
                content: [
                    { type: "text", text: `조회 결과 총 ${historyList.length}건의 데이터를 찾았습니다.` },
                    { type: "text", text: JSON.stringify(historyList, null, 2) }
                ]
            };
        } catch (error) {
            console.error(`수율 이력 조회 중 에러 발생: ${error}`);
            const status = error.response?.status || 'Unknown';
            return { content: [{ type: "text", text: `데이터 조회 실패 (HTTP ${status}): ${error.message}` }], isError: true };
        }
    });
};

/** 3. 상세 조회 핸들러 (BAR/PIPE 공용) */
const handleDetailLookup = async (type, id, token) => {
    const endpoint = type.toLowerCase();
    return withSpan(`tool.get_${endpoint}_yield_detail`, null, {
        'tool.name': `get_${endpoint}_yield_detail`,
        'tool.type': type,
        'tool.id': id
    }, async (span) => {
        try {
            console.log(`[MCP] ${type} 상세 조회 요청: ID=${id}`);
            const response = await axios.get(
                `http://localhost:8481/seed/api/yield/${endpoint}/${id}`,
                { headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } }
            );
            return {
                content: [
                    { type: "text", text: `${type} (ID: ${id})의 상세 정보입니다.` },
                    { type: "text", text: JSON.stringify(response.data, null, 2) }
                ]
            };
        } catch (error) {
            if (error.response?.status === 404) {
                return { content: [{ type: "text", text: `해당 ID(${id})를 가진 ${type} 데이터를 찾을 수 없습니다.` }] };
            }
            return { content: [{ type: "text", text: `에러 발생: ${error.message}` }], isError: true };
        }
    });
};

export { handleGenerateYieldChart, handleDetailLookup, handleFetchYieldHistory }
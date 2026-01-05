import { chromium } from 'playwright';
import * as echarts from 'echarts';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** * 순수 ESM 방식: ECharts 라이브러리 파일 경로 도출
 * node_modules 내의 위치를 직접 계산합니다.
 */
const ECHARTS_PATH = path.resolve(
    __dirname,
    '../node_modules/echarts/dist/echarts.min.js'
);

// ---------------------------------------------------------
// [Logic 1] 데이터 통계 및 가공 로직
// ---------------------------------------------------------

/** Box Plot을 위한 5수치 요약 계산 */
function calculateBoxPlotValues(sortedData) {
    const len = sortedData.length;
    if (len === 0) return [0, 0, 0, 0, 0];

    const min = sortedData[0];
    const max = sortedData[len - 1];

    const getQuantile = (p) => {
        const pos = (len - 1) * p;
        const base = Math.floor(pos);
        const rest = pos - base;
        if (len - 1 > base) {
            return sortedData[base] + rest * (sortedData[base + 1] - sortedData[base]);
        } else {
            return sortedData[base];
        }
    };

    const q1 = parseFloat(getQuantile(0.25).toFixed(2));
    const median = parseFloat(getQuantile(0.5).toFixed(2));
    const q3 = parseFloat(getQuantile(0.75).toFixed(2));

    return [min, q1, median, q3, max];
}

/** 원시 데이터를 ECharts용 데이터 구조로 변환 */
function processChartData(type, historyData) {
    if (!historyData || historyData.length === 0) return { dates: [], avgYields: [], boxPlotValues: [] };

    const monthlyMap = new Map();

    historyData.forEach((item) => {
        const dateStr = item.workDate;
        const monthKey = dateStr.length >= 7 ? dateStr.substring(0, 7) : dateStr;

        // 유효성 검사 (0 이하나 100 초과 값 제외)
        if (type === 'PIPE') {
            const val = Number(item.yieldRate) || 0;
            if (val <= 0 || val > 100) return;
        } else {
            const val = Number(item.finalYield) || 0;
            if (val <= 0 || val > 100) return;
        }

        if (!monthlyMap.has(monthKey)) monthlyMap.set(monthKey, []);
        monthlyMap.get(monthKey).push(item);
    });

    const result = Array.from(monthlyMap.entries()).map(([month, items]) => {
        let avg = 0;
        let values = [];

        if (type === 'PIPE') {
            values = items.map(i => Number(i.yieldRate)).sort((a, b) => a - b);
            const totalProd = items.reduce((acc, i) => acc + (Number(i.prodQty) || 0), 0);
            const totalInput = items.reduce((acc, i) => acc + (Number(i.inputQty) || 0), 0);
            avg = totalInput === 0 ? 0 : parseFloat(((totalProd / totalInput) * 100).toFixed(2));
        } else {
            // BAR
            values = items.map(i => Number(i.finalYield)).sort((a, b) => a - b);
            const totalProd = items.reduce((acc, i) => acc + (Number(i.prodQty) || 0), 0);
            const weightedYieldSum = items.reduce((acc, i) => acc + ((Number(i.finalYield) || 0) * (Number(i.prodQty) || 0)), 0);
            avg = totalProd === 0 ? 0 : parseFloat((weightedYieldSum / totalProd).toFixed(2));
        }

        const boxStats = calculateBoxPlotValues(values);

        return {
            date: month,
            avgYield: avg,
            boxPlotData: boxStats
        };
    });

    result.sort((a, b) => a.date.localeCompare(b.date));

    return {
        dates: result.map(r => r.date),
        avgYields: result.map(r => r.avgYield),
        boxPlotValues: result.map(r => r.boxPlotData)
    };
}

// ---------------------------------------------------------
// [Logic 2] Playwright 캡처 로직
// ---------------------------------------------------------

/** 가공된 데이터를 받아 이미지를 생성하여 Base64로 반환 */
async function generateImage(type, processedData) {
    // 브라우저 실행 (성능을 위해 재사용 로직을 넣을 수도 있지만, 안정성을 위해 여기선 매번 생성/종료)
    const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const context = await browser.newContext({ deviceScaleFactor: 2, viewport: { width: 1000, height: 600 } });
    const page = await context.newPage();

    try {
        const chartOption = {
            animation: false,
            backgroundColor: '#ffffff',
            title: {
                text: type === 'PIPE' ? "월별 수율 분포 및 가중 평균 트렌드" : "월별 최종 수율 분포 및 가중 평균 트렌드",
                left: 'center'
            },
            grid: { left: '3%', right: '4%', bottom: '15%', top: '15%', containLabel: true },
            xAxis: { type: 'category', boundaryGap: true, data: processedData.dates },
            yAxis: { type: 'value', name: '수율(%)', scale: true, splitLine: { show: true, lineStyle: { type: 'dashed' } } },
            series: [
                {
                    name: type === 'PIPE' ? '가중 평균 수율 (Line)' : '가중 평균 최종 수율 (Line)',
                    type: 'line',
                    data: processedData.avgYields,
                    symbolSize: 4,
                    itemStyle: { color: '#fd7e14' },
                    lineStyle: { width: 3 },
                    z: 10
                },
                {
                    name: type === 'PIPE' ? '수율 분포 (Box)' : '최종 수율 분포 (Box)',
                    type: 'boxplot',
                    data: processedData.boxPlotValues,
                    itemStyle: { color: '#ebf3ff', borderColor: '#337ab7', borderWidth: 1.5 }
                }
            ]
        };

        await page.setContent(`
            <html>
                <body style="margin:0; padding:0;">
                    <div id="main" style="width:1000px; height:600px;"></div>
                </body>
            </html>
        `);

        // ECharts 라이브러리 주입
        if (!ECHARTS_PATH) {
            throw new Error("ECharts path not found. Please install echarts package.");
        }

        await page.addScriptTag({ path: ECHARTS_PATH });

        // ECharts 라이브러리가 로드될 때까지 대기
        await page.waitForFunction(() => typeof echarts !== 'undefined', { timeout: 5000 });

        // 브라우저 콘솔 로그 캡처 (디버깅용)
        page.on('console', msg => console.log('Browser Console:', msg.text()));

        const renderResult = await page.evaluate((option) => {
            return new Promise((resolve, reject) => {
                try {
                    console.log('Starting chart rendering...');

                    // ECharts 라이브러리 확인
                    if (typeof echarts === 'undefined') {
                        throw new Error('ECharts library not loaded');
                    }

                    const mainElement = document.getElementById('main');
                    if (!mainElement) {
                        throw new Error('Main element not found');
                    }

                    console.log('Initializing ECharts...');
                    const chart = echarts.init(mainElement);

                    // finished 이벤트 타임아웃 추가 (fallback)
                    const timeout = setTimeout(() => {
                        console.log('Chart rendering timeout - fallback triggered');
                        resolve({ success: true, method: 'timeout' });
                    }, 5000);

                    chart.on('finished', () => {
                        console.log('Chart finished event triggered');
                        clearTimeout(timeout);
                        resolve({ success: true, method: 'finished' });
                    });

                    console.log('Setting chart option...');
                    chart.setOption(option);
                    console.log('Chart option set successfully');
                } catch (error) {
                    console.error('Chart rendering error:', error.message);
                    reject(new Error(`Chart rendering failed: ${error.message}`));
                }
            });
        }, chartOption);

        console.log('Chart render result:', renderResult);

        if (!renderResult.success) {
            throw new Error('Chart rendering failed');
        }

        // 차트 렌더링 완료 후 약간의 대기 (안정화)
        await page.waitForTimeout(500);
        const buffer = await page.screenshot({ type: 'png' });
        return buffer.toString('base64');

    } finally {
        await browser.close();
    }
}

// 외부에서 호출할 메인 함수
async function createYieldChart(type, rawData) {
    const processed = processChartData(type, rawData);

    if (processed.dates.length === 0) {
        throw new Error("유효한 데이터가 없어 차트를 생성할 수 없습니다.");
    }

    const base64Image = await generateImage(type, processed);
    return {
        base64Image,
        count: processed.dates.length
    };
}

export { createYieldChart };
import { trace, context, propagation, SpanStatusCode } from '@opentelemetry/api';
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { Resource } from '@opentelemetry/resources';

const publicKey = process.env.LANGFUSE_PUBLIC_KEY || '';
const secretKey = process.env.LANGFUSE_SECRET_KEY || '';
const host = process.env.LANGFUSE_BASE_URL || '';

if (publicKey && secretKey && host) {
    const auth = Buffer.from(`${publicKey}:${secretKey}`).toString('base64');

    const resource = new Resource({ 'service.name': 'echart-mcp-server' });
    const provider = new NodeTracerProvider({ resource });

    const exporter = new OTLPTraceExporter({
        url: `${host}/api/public/otel/v1/traces`,
        headers: { 'Authorization': `Basic ${auth}` }
    });

    provider.addSpanProcessor(new BatchSpanProcessor(exporter));
    provider.register();  // Sets global tracer provider + W3C propagator

    console.log(`✅ Langfuse OTEL 트레이싱 활성화: ${host}`);

    // Graceful shutdown
    process.on('SIGTERM', () => provider.shutdown());
    process.on('SIGINT', () => provider.shutdown());
} else {
    console.log('ℹ️ Langfuse 설정 없음 — 트레이싱 비활성화');
}

const tracer = trace.getTracer('echart-mcp-server');

/**
 * Extract trace context from HTTP request headers (traceparent)
 * Returns an OpenTelemetry Context that can be used as parent
 */
function extractContext(headers) {
    return propagation.extract(context.active(), headers);
}

/**
 * Run a function within a traced span, optionally with a parent context
 */
async function withSpan(name, parentCtx, attributes, fn) {
    const ctx = parentCtx || context.active();
    return context.with(ctx, async () => {
        const span = tracer.startSpan(name, { attributes }, ctx);
        try {
            const result = await fn(span);
            span.setStatus({ code: SpanStatusCode.OK });
            return result;
        } catch (error) {
            span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
            span.recordException(error);
            throw error;
        } finally {
            span.end();
        }
    });
}

export { tracer, extractContext, withSpan };

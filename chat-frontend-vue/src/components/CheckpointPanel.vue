<template>
  <div :class="['checkpoint-panel', { open }]">
    <div class="panel-backdrop" @click="emit('close')" />
    <div class="panel-content">
      <div class="panel-header">
        <h3 class="panel-title">Checkpoint Graph</h3>
        <button class="panel-close-btn" @click="emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div class="panel-body">
        <!-- Loading state -->
        <div v-if="loading" class="panel-loading">
          <div class="spinner" />
          <span>로딩 중...</span>
        </div>

        <!-- Error state -->
        <div v-else-if="error" class="panel-error">
          <p>{{ error }}</p>
          <button class="retry-btn" @click="emit('retry')">재시도</button>
        </div>

        <!-- Empty state -->
        <div v-else-if="!graph || graph.nodes.length === 0" class="panel-empty">
          <p>체크포인트가 없습니다</p>
        </div>

        <!-- Checkpoint nodes list -->
        <div v-else class="checkpoint-list">
          <div
            v-for="node in graph.nodes"
            :key="node.checkpoint_id"
            :class="['checkpoint-node', { head: node.is_head }]"
            @click="onNodeClick(node)"
          >
            <div class="node-indicator">
              <div class="node-dot" />
              <div class="node-line" />
            </div>
            <div class="node-content">
              <div class="node-header">
                <span class="node-step" v-if="node.step !== null">Step {{ node.step }}</span>
                <span class="node-badge" v-if="node.is_head">HEAD</span>
              </div>
              <div class="node-id">{{ node.checkpoint_id.slice(0, 8) }}...</div>
              <div class="node-source" v-if="node.source">{{ node.source }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CheckpointGraph, CheckpointNode } from '../types/chat';

defineProps<{
  open: boolean;
  graph: CheckpointGraph | null;
  loading: boolean;
  error: string | null;
}>();

const emit = defineEmits<{
  close: [];
  retry: [];
  'node-click': [node: CheckpointNode];
}>();

function onNodeClick(node: CheckpointNode) {
  console.log('[CheckpointPanel] 체크포인트 클릭:', {
    checkpoint_id: node.checkpoint_id,
    step: node.step,
    source: node.source,
    is_head: node.is_head,
  });
  emit('node-click', node);
}
</script>

<style scoped>
/* Overlay wrapper — covers full viewport, pointer-events blocked when closed */
.checkpoint-panel {
  position: fixed;
  inset: 0;
  z-index: 100;
  pointer-events: none;
}

.checkpoint-panel.open {
  pointer-events: auto;
}

/* Semi-transparent backdrop */
.panel-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(2, 6, 23, 0.45);
  backdrop-filter: blur(3px);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.checkpoint-panel.open .panel-backdrop {
  opacity: 1;
}

/* Sliding panel from the right */
.panel-content {
  position: fixed;
  top: 0;
  right: 0;
  height: 100vh;
  width: 320px;
  background: var(--glass-bg);
  backdrop-filter: blur(40px) saturate(1.5);
  border-left: 1px solid var(--glass-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: var(--font);
  transform: translateX(100%);
  transition: transform 0.3s ease;
}

.checkpoint-panel.open .panel-content {
  transform: translateX(0);
}

/* Header */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid var(--glass-border);
  flex-shrink: 0;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-0);
}

.panel-close-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: var(--text-2);
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  flex-shrink: 0;
}

.panel-close-btn:hover {
  background: var(--glass-hover);
  border-color: var(--glass-border);
  color: var(--text-1);
}

/* Scrollable body */
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
}

.panel-body::-webkit-scrollbar {
  width: 4px;
}

.panel-body::-webkit-scrollbar-thumb {
  background: var(--glass-border);
  border-radius: 2px;
}

/* Loading state */
.panel-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 200px;
  color: var(--text-2);
  font-size: 13px;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--glass-border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Error state */
.panel-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px 16px;
  text-align: center;
}

.panel-error p {
  margin: 0;
  font-size: 13px;
  color: #fecaca;
  line-height: 1.5;
}

.retry-btn {
  padding: 7px 14px;
  border: 1px solid color-mix(in srgb, var(--accent) 50%, transparent);
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.retry-btn:hover {
  background: color-mix(in srgb, var(--accent) 18%, transparent);
}

/* Empty state */
.panel-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-2);
  font-size: 13px;
}

.panel-empty p {
  margin: 0;
}

/* Checkpoint list — vertical timeline */
.checkpoint-list {
  display: flex;
  flex-direction: column;
}

.checkpoint-node {
  display: flex;
  gap: 12px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  padding: 10px 8px;
  transition: background 0.2s ease;
}

.checkpoint-node:hover {
  background: var(--glass-bg);
}

/* Timeline indicator (dot + line) */
.node-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 10px;
  padding-top: 3px;
}

.node-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--text-2);
  border: 2px solid var(--glass-border);
  flex-shrink: 0;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.checkpoint-node.head .node-dot {
  background: var(--accent);
  border-color: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent);
}

.node-line {
  flex: 1;
  width: 2px;
  min-height: 24px;
  background: var(--glass-border);
  margin-top: 4px;
}

/* Hide line on last node */
.checkpoint-node:last-child .node-line {
  display: none;
}

/* Node content */
.node-content {
  flex: 1;
  min-width: 0;
  padding-bottom: 16px;
}

.checkpoint-node:last-child .node-content {
  padding-bottom: 0;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.node-step {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-0);
}

/* HEAD badge */
.node-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  background: color-mix(in srgb, var(--accent) 18%, transparent);
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
}

.node-id {
  font-size: 11.5px;
  font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  color: var(--text-2);
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-source {
  font-size: 12px;
  color: var(--text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

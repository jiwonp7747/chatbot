<template>
  <div class="chat-header">
    <h2 class="chat-title">{{ session.title }}</h2>
    <ModelSelector
      :selected-model="session.model"
      @model-change="emit('model-change', $event)"
    />
  </div>
  <div class="messages-container" ref="messagesContainerRef">
    <ChatMessage
      v-for="message in session.messages"
      :key="message.id"
      :message="message"
    />
    <ChatMessage
      v-if="isStreaming && streamingContent && !store.pendingConfirm"
      :message="{
        id: 'streaming',
        role: 'assistant',
        content: streamingContent,
        timestamp: Date.now()
      }"
    />
    <!-- 서브에이전트 도구 호출 진행 상황 -->
    <div v-if="currentSubProgress.length > 0" class="sub-progress-list">
      <div
        v-for="group in groupedSubProgress"
        :key="group.agent"
        class="sub-progress-group"
      >
        <!-- Agent header: only shown when multiple agents are active -->
        <div v-if="showAgentHeaders" class="sub-progress-agent-label">
          {{ group.agent }}
        </div>

        <!-- Collapsed older completed items summary -->
        <div
          v-if="group.collapsedCount > 0"
          class="sub-progress-collapsed"
        >
          {{ group.collapsedCount }}개 완료됨
        </div>

        <!-- Visible entries -->
        <div
          v-for="(entry, idx) in group.visibleEntries"
          :key="idx"
          class="sub-progress-item"
          :class="getEntryStatus(entry.content)"
        >
          <span class="sub-progress-indicator">
            <span v-if="getEntryStatus(entry.content) === 'calling'" class="indicator-dot"></span>
            <span v-else-if="getEntryStatus(entry.content) === 'completed'" class="indicator-check">✓</span>
            <span v-else class="indicator-fail">✗</span>
          </span>
          <span class="sub-progress-content">{{ entry.content }}</span>
        </div>
      </div>
    </div>
    <!-- HITL 도구 실행 확인 카드 -->
    <div v-if="store.pendingConfirm" class="confirm-card">
      <div class="confirm-icon">&#128270;</div>
      <div class="confirm-title">'{{ store.pendingConfirm.toolName }}' 실행 확인</div>
      <div class="confirm-args" v-if="Object.keys(store.pendingConfirm.toolArgs).length">
        <pre>{{ JSON.stringify(store.pendingConfirm.toolArgs, null, 2) }}</pre>
      </div>
      <div class="confirm-actions">
        <button class="btn-approve" @click="store.approveToolCall()">승인</button>
        <button class="btn-reject" @click="store.rejectToolCall()">거부</button>
      </div>
    </div>
    <div ref="messagesEndRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, computed } from 'vue';
import ChatMessage from '../components/ChatMessage.vue';
import ModelSelector from '../components/ModelSelector.vue';
import { useChatStore } from '../stores/chatStore';
import type { ChatSession, ModelType } from '../types/chat';

const store = useChatStore();

const props = defineProps<{
  session: ChatSession;
  streamingContent: string;
  isStreaming: boolean;
}>();

const emit = defineEmits<{
  'model-change': [model: ModelType];
}>();

const currentSubProgress = computed(() => {
  const numericId = parseInt(props.session.id);
  return store.subProgressMap[numericId] || [];
});

type EntryStatus = 'calling' | 'completed' | 'failed';

function getEntryStatus(content: string): EntryStatus {
  if (content.includes('완료')) return 'completed';
  if (content.includes('실패')) return 'failed';
  return 'calling';
}

const VISIBLE_LIMIT = 6;

interface SubProgressGroup {
  agent: string;
  collapsedCount: number;
  visibleEntries: typeof currentSubProgress.value;
}

const groupedSubProgress = computed<SubProgressGroup[]>(() => {
  const entries = currentSubProgress.value;

  // Collect ordered agents (preserving first-seen order)
  const agentOrder: string[] = [];
  const agentMap: Record<string, typeof entries> = {};

  for (const entry of entries) {
    const agent = entry.agent || 'agent';
    if (!agentMap[agent]) {
      agentMap[agent] = [];
      agentOrder.push(agent);
    }
    agentMap[agent].push(entry);
  }

  return agentOrder.map((agent) => {
    const all = agentMap[agent];

    // Separate completed-at-the-front from the rest
    // We collapse the oldest completed entries when total > VISIBLE_LIMIT
    const completedIndices: number[] = [];
    for (let i = 0; i < all.length; i++) {
      const s = getEntryStatus(all[i].content);
      if (s === 'completed') completedIndices.push(i);
    }

    const overflow = all.length - VISIBLE_LIMIT;
    const collapseCount = overflow > 0 ? Math.min(overflow, completedIndices.length) : 0;
    const collapsedSet = new Set(completedIndices.slice(0, collapseCount));

    return {
      agent,
      collapsedCount: collapseCount,
      visibleEntries: all.filter((_, i) => !collapsedSet.has(i)),
    };
  });
});

const showAgentHeaders = computed(() => {
  return groupedSubProgress.value.length > 1;
});

const messagesEndRef = ref<HTMLDivElement>();
const messagesContainerRef = ref<HTMLDivElement>();

function scrollToBottom() {
  nextTick(() => {
    messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' });
  });
}

onMounted(() => {
  scrollToBottom();
});

watch(
  () => [props.session.messages, props.streamingContent, currentSubProgress.value],
  () => {
    scrollToBottom();
  },
  { deep: true }
);
</script>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  border-bottom: 1px solid var(--glass-border);
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  position: relative;
  z-index: 1;
}

.chat-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-0);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  letter-spacing: -0.2px;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
}

.sub-progress-list {
  max-width: 720px;
  margin: 4px auto 8px;
  padding: 0 32px 0 64px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── Group ── */
.sub-progress-group {
  display: flex;
  flex-direction: column;
  gap: 1px;
  border-left: 1.5px solid var(--glass-border, rgba(255,255,255,0.1));
  padding-left: 10px;
  animation: fadeIn 0.25s ease;
}

.sub-progress-agent-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-2, rgba(255,255,255,0.3));
  margin-bottom: 2px;
  padding-bottom: 2px;
}

/* ── Collapsed summary ── */
.sub-progress-collapsed {
  font-size: 11px;
  color: var(--text-2, rgba(255,255,255,0.3));
  padding: 1px 0;
  font-style: italic;
}

/* ── Item base ── */
.sub-progress-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 2px 0;
  animation: fadeIn 0.3s ease;
  transition: color 0.3s ease, opacity 0.3s ease;
}

/* ── Status variants ── */
.sub-progress-item.calling {
  color: var(--text-2, rgba(255,255,255,0.42));
  animation: fadeIn 0.3s ease, shimmer 2.4s ease-in-out infinite;
}

.sub-progress-item.completed {
  color: var(--text-1, rgba(255,255,255,0.62));
}

.sub-progress-item.failed {
  color: rgba(255, 90, 90, 0.82);
}

/* ── Content ── */
.sub-progress-content {
  line-height: 1.4;
}

/* ── Indicators ── */
.sub-progress-indicator {
  flex-shrink: 0;
  width: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Spinning dot for "calling" */
.indicator-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  border-top-color: transparent;
  animation: spin 0.8s linear infinite;
  opacity: 0.7;
}

/* Checkmark for "completed" */
.indicator-check {
  font-size: 11px;
  color: rgba(100, 210, 140, 0.85);
  line-height: 1;
}

/* X for "failed" */
.indicator-fail {
  font-size: 11px;
  color: rgba(255, 90, 90, 0.85);
  line-height: 1;
}

/* ── Keyframes ── */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes shimmer {
  0%,  100% { opacity: 0.55; }
  50%        { opacity: 0.85; }
}

.confirm-card {
  max-width: 480px;
  margin: 16px auto;
  padding: 20px 24px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  text-align: center;
}

.confirm-icon {
  font-size: 28px;
  margin-bottom: 8px;
}

.confirm-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-0);
  margin-bottom: 12px;
}

.confirm-args {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
  text-align: left;
  overflow-x: auto;
}

.confirm-args pre {
  margin: 0;
  font-size: 12px;
  color: var(--text-1);
  white-space: pre-wrap;
  word-break: break-all;
}

.confirm-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.btn-approve,
.btn-reject {
  padding: 8px 24px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-approve {
  background: var(--accent);
  color: #fff;
}

.btn-reject {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-1);
  border: 1px solid var(--glass-border);
}

.btn-approve:hover,
.btn-reject:hover {
  opacity: 0.85;
}
</style>

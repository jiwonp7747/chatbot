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
      <!-- 기본 모드 -->
      <template v-if="!store.pendingConfirm.isEditing">
        <div class="confirm-header">
          <span class="confirm-icon">&#128270;</span>
          <span class="confirm-title">도구 실행 확인 ({{ store.pendingConfirm.toolCalls.length }}건)</span>
        </div>
        <div v-if="store.pendingConfirm.toolContext" class="confirm-context">
          <div class="confirm-context-label">💬 에이전트 판단</div>
          <div class="confirm-context-text">{{ store.pendingConfirm.toolContext }}</div>
        </div>
        <div
          v-for="(tc, idx) in store.pendingConfirm.toolCalls"
          :key="idx"
          class="confirm-tool-item"
        >
          <div class="confirm-args-label">⚙️ {{ tc.detail?.tool_name || tc.name }}</div>
          <div v-if="tc.detail?.description" class="confirm-tool-detail">{{ tc.detail.description }}</div>
          <pre>{{ JSON.stringify(tc.args, null, 2) }}</pre>
        </div>
        <div class="confirm-actions">
          <button class="btn-approve" @click="store.approveToolCall()">승인</button>
          <button class="btn-edit" @click="store.toggleEditMode()">수정</button>
          <button class="btn-reject" @click="store.toggleRejectMode()">거부</button>
        </div>
        <!-- 거부 모드: 메시지 입력 -->
        <template v-if="store.pendingConfirm.isRejecting">
          <div class="reject-section">
            <textarea
              v-model="store.pendingConfirm.rejectMessage"
              class="edit-textarea"
              rows="2"
              placeholder="거부 사유 또는 지시사항 (선택, 예: 다른 LOT로 조회해줘)"
              spellcheck="false"
            />
            <div class="confirm-actions">
              <button class="btn-reject-confirm" @click="store.submitReject()">거부 확인</button>
              <button class="btn-cancel" @click="store.toggleRejectMode()">취소</button>
            </div>
          </div>
        </template>
      </template>
      <!-- 수정 모드 (스키마 기반 폼) -->
      <template v-else>
        <div class="confirm-header">
          <span class="confirm-icon">✏️</span>
          <span class="confirm-title">도구 인자 수정</span>
        </div>
        <div v-if="store.pendingConfirm.schemasLoading" class="schema-loading">
          스키마 로딩 중...
        </div>
        <template v-else>
          <div
            v-for="(tc, idx) in store.pendingConfirm.toolCalls"
            :key="idx"
            class="edit-tool-section"
          >
            <!-- 도구 선택 -->
            <div class="edit-field">
              <label class="edit-label">도구</label>
              <select
                class="edit-select"
                :value="store.pendingConfirm.editedToolNames[idx] || tc.name"
                @change="store.onToolNameChange(idx, ($event.target as HTMLSelectElement).value)"
              >
                <option
                  v-for="tool in store.pendingConfirm.availableTools"
                  :key="tool.name"
                  :value="tool.name"
                >{{ tool.name }} — {{ tool.description }}</option>
              </select>
            </div>
            <!-- 스키마 기반 인자 폼 -->
            <template v-if="getToolSchema(idx)?.schema?.properties">
              <div
                v-for="(prop, propName) in getToolSchema(idx)!.schema.properties"
                :key="String(propName)"
                class="edit-field"
              >
                <label class="edit-label">
                  {{ String(propName) }}
                  <span v-if="isRequired(idx, String(propName))" class="field-required">*</span>
                </label>
                <span v-if="prop.description" class="field-desc">{{ prop.description }}</span>
                <!-- enum → select -->
                <select
                  v-if="prop.enum"
                  class="edit-select"
                  :value="store.pendingConfirm!.editedArgs[idx]?.[String(propName)] ?? prop.default ?? ''"
                  @change="updateArg(idx, String(propName), ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">-- 선택 --</option>
                  <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <!-- boolean → checkbox -->
                <input
                  v-else-if="resolveType(prop) === 'boolean'"
                  type="checkbox"
                  class="edit-checkbox"
                  :checked="!!store.pendingConfirm!.editedArgs[idx]?.[String(propName)]"
                  @change="updateArg(idx, String(propName), ($event.target as HTMLInputElement).checked)"
                />
                <!-- integer/number → number input -->
                <input
                  v-else-if="resolveType(prop) === 'integer' || resolveType(prop) === 'number'"
                  type="number"
                  class="edit-input"
                  :value="store.pendingConfirm!.editedArgs[idx]?.[String(propName)] ?? prop.default ?? ''"
                  @input="updateArg(idx, String(propName), Number(($event.target as HTMLInputElement).value))"
                />
                <!-- string (datetime hint) -->
                <input
                  v-else-if="resolveType(prop) === 'string' && isDateTimeField(prop)"
                  type="datetime-local"
                  class="edit-input"
                  :value="toDateTimeLocal(store.pendingConfirm!.editedArgs[idx]?.[String(propName)])"
                  @input="updateArg(idx, String(propName), fromDateTimeLocal(($event.target as HTMLInputElement).value))"
                />
                <!-- string (default) -->
                <input
                  v-else-if="resolveType(prop) === 'string'"
                  type="text"
                  class="edit-input"
                  :value="store.pendingConfirm!.editedArgs[idx]?.[String(propName)] ?? prop.default ?? ''"
                  @input="updateArg(idx, String(propName), ($event.target as HTMLInputElement).value)"
                />
                <!-- array → comma-separated -->
                <input
                  v-else-if="resolveType(prop) === 'array'"
                  type="text"
                  class="edit-input"
                  placeholder="쉼표로 구분"
                  :value="arrayToString(store.pendingConfirm!.editedArgs[idx]?.[String(propName)])"
                  @input="updateArg(idx, String(propName), stringToArray(($event.target as HTMLInputElement).value))"
                />
                <!-- fallback → JSON textarea -->
                <textarea
                  v-else
                  class="edit-textarea"
                  rows="2"
                  :value="JSON.stringify(store.pendingConfirm!.editedArgs[idx]?.[String(propName)] ?? prop.default ?? null, null, 2)"
                  @input="updateArgJson(idx, String(propName), ($event.target as HTMLTextAreaElement).value)"
                />
              </div>
            </template>
            <!-- 스키마 없음 → JSON fallback -->
            <template v-else>
              <div class="edit-field">
                <label class="edit-label">인자 (JSON)</label>
                <textarea
                  class="edit-textarea"
                  rows="4"
                  :value="JSON.stringify(store.pendingConfirm!.editedArgs[idx] || tc.args, null, 2)"
                  @input="updateArgJson(idx, '__raw__', ($event.target as HTMLTextAreaElement).value)"
                />
              </div>
            </template>
          </div>
        </template>
        <div class="confirm-actions">
          <button class="btn-approve" @click="store.submitEditedToolCall()">수정 실행</button>
          <button class="btn-cancel" @click="store.toggleEditMode()">취소</button>
        </div>
      </template>
    </div>
    <div ref="messagesEndRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, computed } from 'vue';
import ChatMessage from '../components/ChatMessage.vue';
import ModelSelector from '../components/ModelSelector.vue';
import { useChatStore } from '../stores/chatStore';
import type { ChatSession, ModelType, JsonSchemaProperty, ToolSchema } from '../types/chat';

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

// ── HITL 수정 폼 헬퍼 ──

function resolveType(prop: JsonSchemaProperty): string {
  if (prop.type) return prop.type;
  // Pydantic Optional: anyOf: [{type: "string"}, {type: "null"}]
  if (prop.anyOf) {
    const nonNull = prop.anyOf.find(t => t.type !== 'null');
    return nonNull?.type || 'string';
  }
  return 'string';
}

function isDateTimeField(prop: JsonSchemaProperty): boolean {
  // Pydantic datetime → anyOf 내부에 format: "date-time" 존재
  if (prop.anyOf?.some(v => v.format === 'date-time')) return true;
  if (prop.format === 'date-time') return true;
  // fallback: description 기반
  const desc = (prop.description || '').toLowerCase();
  return desc.includes('iso 8601') || desc.includes('iso8601');
}

function toDateTimeLocal(val: unknown): string {
  if (!val || typeof val !== 'string') return '';
  // "2026-02-26T00:00:00Z" → "2026-02-26T00:00"
  return val.replace(/Z$/, '').slice(0, 16);
}

function fromDateTimeLocal(val: string): string {
  if (!val) return '';
  return val + ':00Z';
}

function arrayToString(val: unknown): string {
  if (Array.isArray(val)) return val.join(', ');
  return '';
}

function stringToArray(val: string): string[] {
  return val.split(',').map(s => s.trim()).filter(Boolean);
}

function getToolSchema(idx: number): ToolSchema | undefined {
  if (!store.pendingConfirm) return undefined;
  const toolName = store.pendingConfirm.editedToolNames[idx] || store.pendingConfirm.toolCalls[idx]?.name;
  return store.pendingConfirm.toolSchemas[toolName];
}

function isRequired(idx: number, propName: string): boolean {
  const schema = getToolSchema(idx);
  return schema?.schema?.required?.includes(propName) || false;
}

function updateArg(idx: number, key: string, value: unknown) {
  if (!store.pendingConfirm) return;
  if (!store.pendingConfirm.editedArgs[idx]) {
    store.pendingConfirm.editedArgs[idx] = {};
  }
  store.pendingConfirm.editedArgs[idx][key] = value;
}

function updateArgJson(idx: number, key: string, raw: string) {
  if (!store.pendingConfirm) return;
  try {
    const parsed = JSON.parse(raw);
    if (key === '__raw__') {
      store.pendingConfirm.editedArgs[idx] = parsed;
    } else {
      if (!store.pendingConfirm.editedArgs[idx]) {
        store.pendingConfirm.editedArgs[idx] = {};
      }
      store.pendingConfirm.editedArgs[idx][key] = parsed;
    }
  } catch {
    // JSON 파싱 실패 시 무시 (타이핑 중)
  }
}

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
  max-width: 640px;
  margin: 16px auto;
  padding: 20px 24px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.confirm-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.confirm-icon {
  font-size: 22px;
  flex-shrink: 0;
}

.confirm-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-0);
}

/* 에이전트 판단 근거 */
.confirm-context {
  margin-bottom: 14px;
  padding: 12px;
  background: rgba(100, 180, 255, 0.06);
  border: 1px solid rgba(100, 180, 255, 0.12);
  border-radius: 10px;
}

.confirm-context-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}

.confirm-context-text {
  font-size: 13px;
  color: var(--text-1);
  line-height: 1.55;
  white-space: pre-wrap;
}

/* 도구 항목 */
.confirm-tool-item {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
  text-align: left;
  overflow-x: auto;
}

.confirm-args-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}

.confirm-tool-detail {
  font-size: 13px;
  color: var(--text-1);
  line-height: 1.55;
  margin-bottom: 8px;
  white-space: pre-wrap;
}

.confirm-tool-item pre {
  margin: 0;
  font-size: 12px;
  color: var(--text-1);
  white-space: pre-wrap;
  word-break: break-all;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 8px;
}

/* 버튼 */
.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

.btn-approve,
.btn-edit,
.btn-reject,
.btn-cancel {
  padding: 8px 20px;
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

.btn-edit {
  background: rgba(255, 200, 60, 0.15);
  color: rgba(255, 210, 80, 0.95);
  border: 1px solid rgba(255, 200, 60, 0.2);
}

.btn-reject,
.btn-cancel {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-1);
  border: 1px solid var(--glass-border);
}

.btn-approve:hover,
.btn-edit:hover,
.btn-reject:hover,
.btn-cancel:hover {
  opacity: 0.85;
}

/* 수정 모드 필드 */
.edit-field {
  margin-bottom: 14px;
}

.edit-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-2);
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}

/* 수정 모드 2열 레이아웃 */
.edit-layout {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
}

.edit-left {
  flex: 1;
  min-width: 0;
}

.edit-right {
  flex-shrink: 0;
  width: 180px;
}

.edit-tool-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 140px;
  overflow-y: auto;
  padding: 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  border: 1px solid var(--glass-border);
}

.edit-tool-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 4px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.edit-tool-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.edit-tool-checkbox {
  accent-color: var(--accent);
  cursor: pointer;
}

.edit-tool-name {
  font-size: 12px;
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.edit-textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--glass-border);
  background: rgba(0, 0, 0, 0.25);
  color: var(--text-1);
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  line-height: 1.5;
  resize: vertical;
  box-sizing: border-box;
}

.edit-textarea:focus {
  outline: none;
  border-color: var(--accent);
}

/* 수정 모드: 스키마 기반 폼 */
.schema-loading {
  text-align: center;
  padding: 16px;
  font-size: 12px;
  color: var(--text-2);
}

.edit-tool-section {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}

.edit-select {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--glass-border);
  background: rgba(0, 0, 0, 0.25);
  color: var(--text-1);
  font-size: 12px;
  box-sizing: border-box;
  cursor: pointer;
}

.edit-select:focus {
  outline: none;
  border-color: var(--accent);
}

.edit-input {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--glass-border);
  background: rgba(0, 0, 0, 0.25);
  color: var(--text-1);
  font-size: 12px;
  box-sizing: border-box;
}

.edit-input:focus {
  outline: none;
  border-color: var(--accent);
}

.edit-checkbox {
  accent-color: var(--accent);
  cursor: pointer;
  width: 16px;
  height: 16px;
}

.field-required {
  color: rgba(255, 100, 100, 0.85);
  margin-left: 2px;
}

.field-desc {
  display: block;
  font-size: 10px;
  color: var(--text-2);
  margin-bottom: 4px;
  line-height: 1.4;
}

/* 거부 모드 */
.reject-section {
  margin-top: 12px;
  animation: fadeIn 0.2s ease;
}

.btn-reject-confirm {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: opacity 0.15s;
  background: rgba(255, 90, 90, 0.2);
  color: rgba(255, 120, 120, 0.95);
  border: 1px solid rgba(255, 90, 90, 0.25);
}

.btn-reject-confirm:hover {
  opacity: 0.85;
}
</style>

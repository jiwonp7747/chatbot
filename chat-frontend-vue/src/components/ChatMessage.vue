<template>
  <div :class="['message', message.role]">
    <div class="msg-avatar">
      {{ message.role === 'user' ? avatarInitial : message.role === 'tool' ? '⚙' : 'Bi' }}
    </div>
    <div class="msg-body">
      <div class="msg-meta">
        <span class="msg-name">{{ message.role === 'user' ? 'You' : message.role === 'tool' ? `Tool Result - ${message.tool_name || 'unknown'}` : 'Bistelligence' }}</span>
        <span class="msg-time">{{ formatTime(message.timestamp) }}</span>
      </div>
      <div class="msg-content" v-html="renderedContent" />
      <!-- 서브에이전트 메시지 (접기/펼치기) -->
      <div v-if="message.sub_messages && message.sub_messages.length > 0" class="sub-messages">
        <button class="sub-messages-toggle" @click="subMessagesExpanded = !subMessagesExpanded">
          <svg :class="['toggle-icon', { expanded: subMessagesExpanded }]" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
          {{ message.agent_name || '서브에이전트' }} 대화 내역 ({{ message.sub_messages.length }}개)
        </button>
        <div v-if="subMessagesExpanded" class="sub-messages-list">
          <div
            v-for="sub in message.sub_messages"
            :key="sub.id"
            :class="['sub-message', sub.role]"
          >
            <span class="sub-role">{{ sub.role === 'user' ? '입력' : sub.role === 'assistant' ? 'AI' : sub.tool_name || 'Tool' }}</span>
            <span class="sub-content">{{ sub.content }}</span>
          </div>
        </div>
      </div>
      <!-- Tool message 액션 버튼 -->
      <div v-if="message.role === 'tool' && message.data_ref_type" class="tool-actions">
        <button
          v-if="message.data_ref_type === 'artifact'"
          class="tool-action-btn artifact-btn"
          :disabled="isLoadingArtifact"
          @click="handleViewArtifact"
        >
          {{ isLoadingArtifact ? '로딩 중...' : '📊 데이터 조회' }}
        </button>
        <button
          v-if="message.data_ref_type === 'file'"
          class="tool-action-btn file-btn"
          @click="handleDownloadFile"
        >
          📥 다운로드
        </button>
      </div>
      <!-- Artifact 테이블 뷰 -->
      <div v-if="artifactData" class="artifact-table-container">
        <div class="artifact-table-header">
          <span class="artifact-table-title">{{ artifactData.tool_name || '결과' }}</span>
          <button class="artifact-close-btn" @click="artifactData = null">✕</button>
        </div>
        <div v-if="artifactTableData" class="artifact-table-wrap">
          <table class="artifact-table">
            <thead>
              <tr>
                <th v-for="col in artifactTableData.columns" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in artifactTableData.rows" :key="idx">
                <td v-for="(cell, cidx) in row" :key="cidx">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="artifact-raw">
          <pre>{{ JSON.stringify(artifactData.data, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useMarkdown } from '../composables/useMarkdown';
import { useChatStore } from '../stores/chatStore';
import { getToolResultDownloadUrl } from '../config/api';
import { chatService } from '../services/chatService';
import type { Message, ToolResultData } from '../types/chat';

const props = defineProps<{
  message: Message;
}>();

const { renderMarkdown } = useMarkdown();
const chatStore = useChatStore();

const avatarInitial = 'J';

const renderedContent = computed(() => renderMarkdown(props.message.content));

// tool 메시지 렌더링 시 data_ref_type 로그
if (props.message.role === 'tool') {
  console.log('[ToolMessage] 렌더링', {
    toolName: props.message.tool_name,
    toolCallId: props.message.tool_call_id,
    dataRefType: props.message.data_ref_type ?? 'null',
  });
}

const subMessagesExpanded = ref(false);
const isLoadingArtifact = ref(false);
const artifactData = ref<ToolResultData | null>(null);

const artifactTableData = computed(() => {
  if (!artifactData.value?.data) return null;
  const data = artifactData.value.data as Record<string, unknown>;
  if (data.type === 'table' && Array.isArray(data.columns) && Array.isArray(data.rows)) {
    return { columns: data.columns as string[], rows: data.rows as unknown[][] };
  }
  return null;
});

async function handleViewArtifact() {
  if (!props.message.tool_call_id || !chatStore.currentSessionId) return;
  console.log('[ToolAction] 데이터 조회 클릭', {
    action: 'artifact',
    threadId: chatStore.currentSessionId,
    toolCallId: props.message.tool_call_id,
    toolName: props.message.tool_name,
  });
  isLoadingArtifact.value = true;
  try {
    artifactData.value = await chatService.fetchToolResult(
      chatStore.currentSessionId,
      props.message.tool_call_id,
    );
    console.log('[ToolAction] artifact 응답 수신', artifactData.value);
  } catch (e) {
    console.error('[ToolAction] artifact 조회 실패:', e);
  } finally {
    isLoadingArtifact.value = false;
  }
}

function handleDownloadFile() {
  if (!props.message.tool_call_id || !chatStore.currentSessionId) return;
  const url = getToolResultDownloadUrl(chatStore.currentSessionId, props.message.tool_call_id);
  console.log('[ToolAction] 파일 다운로드 클릭', {
    action: 'file',
    threadId: chatStore.currentSessionId,
    toolCallId: props.message.tool_call_id,
    toolName: props.message.tool_name,
    downloadUrl: url,
  });
  window.open(url, '_blank');
}

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit'
  });
}
</script>

<style scoped>
/* Glass Noir Message Container */
.message {
  display: flex;
  gap: 16px;
  padding: 20px 32px;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  animation: fadeUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Avatar */
.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.message.user .msg-avatar {
  background: linear-gradient(135deg, rgba(129,140,248,0.15), rgba(129,140,248,0.05));
  border: 1px solid rgba(129,140,248,0.2);
  color: var(--accent);
}

.message.assistant .msg-avatar {
  background: linear-gradient(135deg, rgba(52,211,153,0.15), rgba(52,211,153,0.05));
  border: 1px solid rgba(52,211,153,0.2);
  color: var(--emerald);
}

.message.tool .msg-avatar {
  background: linear-gradient(135deg, rgba(251,191,36,0.15), rgba(251,191,36,0.05));
  border: 1px solid rgba(251,191,36,0.2);
  color: #fbbf24;
  font-size: 16px;
}

/* Message Body */
.msg-body {
  flex: 1;
  min-width: 0;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.msg-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-0);
}

.msg-time {
  font-size: 11px;
  color: var(--text-2);
  font-family: var(--mono);
}

.msg-content {
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--text-1);
}

/* Markdown Styles */
.msg-content :deep(p) {
  margin-bottom: 12px;
}

.msg-content :deep(p:last-child) {
  margin-bottom: 0;
}

.msg-content :deep(h1),
.msg-content :deep(h2),
.msg-content :deep(h3),
.msg-content :deep(h4) {
  margin: 16px 0 8px;
  font-weight: 600;
}

.msg-content :deep(h1) { font-size: 24px; }
.msg-content :deep(h2) { font-size: 20px; }
.msg-content :deep(h3) { font-size: 18px; }
.msg-content :deep(h4) { font-size: 16px; }

.msg-content :deep(ul),
.msg-content :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.msg-content :deep(li) {
  margin: 4px 0;
}

.msg-content :deep(code) {
  font-family: var(--mono);
  font-size: 13px;
  background: rgba(129,140,248,0.08);
  padding: 2px 7px;
  border-radius: 5px;
  color: var(--accent);
  border: 1px solid rgba(129,140,248,0.1);
}

.msg-content :deep(pre) {
  background: rgba(0,0,0,0.4);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  padding: 16px 20px;
  margin: 12px 0;
  overflow-x: auto;
}

.msg-content :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
  color: var(--text-1);
  font-size: 13px;
  line-height: 1.6;
}

.msg-content :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.msg-content :deep(a:hover) {
  text-decoration: underline;
}

.msg-content :deep(blockquote) {
  border-left: 4px solid var(--glass-border);
  padding-left: 16px;
  margin: 12px 0;
  color: var(--text-2);
}

.msg-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.msg-content :deep(th),
.msg-content :deep(td) {
  border: 1px solid var(--glass-border);
  padding: 8px 12px;
  text-align: left;
}

.msg-content :deep(th) {
  background: var(--glass-bg);
  font-weight: 600;
}

.msg-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--glass-border);
  margin: 16px 0;
}

.msg-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 12px 0;
}

/* Syntax Highlighting - Glass Noir */
.msg-content :deep(pre code.hljs) {
  background: #0d0d14;
  color: #abb2bf;
  padding: 16px;
  border-radius: 12px;
}

/* YAML */
.msg-content :deep(pre code.language-yaml .hljs-attr),
.msg-content :deep(pre code.language-yml .hljs-attr) {
  color: #e06c75 !important;
}

.msg-content :deep(pre code.language-yaml .hljs-string),
.msg-content :deep(pre code.language-yml .hljs-string) {
  color: #98c379 !important;
}

.msg-content :deep(pre code.language-yaml .hljs-number),
.msg-content :deep(pre code.language-yml .hljs-number) {
  color: #98c379 !important;
}

.msg-content :deep(pre code.language-yaml .hljs-literal),
.msg-content :deep(pre code.language-yml .hljs-literal) {
  color: #98c379 !important;
}

/* Text, Bash, Shell */
.msg-content :deep(pre code.language-text),
.msg-content :deep(pre code.language-bash),
.msg-content :deep(pre code.language-sh),
.msg-content :deep(pre code.language-shell),
.msg-content :deep(pre code.language-plaintext) {
  color: #e6e6e6 !important;
}

.msg-content :deep(pre code.language-text *),
.msg-content :deep(pre code.language-bash *),
.msg-content :deep(pre code.language-sh *),
.msg-content :deep(pre code.language-shell *),
.msg-content :deep(pre code.language-plaintext *) {
  color: #e6e6e6 !important;
}

/* JavaScript/TypeScript */
.msg-content :deep(pre code.language-javascript .hljs-keyword),
.msg-content :deep(pre code.language-typescript .hljs-keyword),
.msg-content :deep(pre code.language-js .hljs-keyword),
.msg-content :deep(pre code.language-ts .hljs-keyword) {
  color: #c678dd;
}

.msg-content :deep(pre code.language-javascript .hljs-function),
.msg-content :deep(pre code.language-typescript .hljs-function),
.msg-content :deep(pre code.language-js .hljs-function),
.msg-content :deep(pre code.language-ts .hljs-function) {
  color: #61afef;
}

.msg-content :deep(pre code.language-javascript .hljs-string),
.msg-content :deep(pre code.language-typescript .hljs-string),
.msg-content :deep(pre code.language-js .hljs-string),
.msg-content :deep(pre code.language-ts .hljs-string) {
  color: #98c379;
}

.msg-content :deep(pre code.language-javascript .hljs-number),
.msg-content :deep(pre code.language-typescript .hljs-number),
.msg-content :deep(pre code.language-js .hljs-number),
.msg-content :deep(pre code.language-ts .hljs-number) {
  color: #d19a66;
}

/* Python */
.msg-content :deep(pre code.language-python .hljs-keyword) {
  color: #c678dd;
}

.msg-content :deep(pre code.language-python .hljs-string) {
  color: #98c379;
}

.msg-content :deep(pre code.language-python .hljs-number) {
  color: #d19a66;
}

.msg-content :deep(pre code.language-python .hljs-function) {
  color: #61afef;
}

/* JSON */
.msg-content :deep(pre code.language-json .hljs-attr) {
  color: #e06c75;
}

.msg-content :deep(pre code.language-json .hljs-string) {
  color: #98c379;
}

.msg-content :deep(pre code.language-json .hljs-number),
.msg-content :deep(pre code.language-json .hljs-literal) {
  color: #d19a66;
}

/* HTML/CSS */
.msg-content :deep(pre code.language-html .hljs-tag),
.msg-content :deep(pre code.language-xml .hljs-tag) {
  color: #e06c75;
}

.msg-content :deep(pre code.language-html .hljs-name),
.msg-content :deep(pre code.language-xml .hljs-name) {
  color: #e06c75;
}

.msg-content :deep(pre code.language-html .hljs-attr),
.msg-content :deep(pre code.language-xml .hljs-attr) {
  color: #d19a66;
}

.msg-content :deep(pre code.language-css .hljs-selector-tag),
.msg-content :deep(pre code.language-css .hljs-selector-class),
.msg-content :deep(pre code.language-css .hljs-selector-id) {
  color: #e06c75;
}

.msg-content :deep(pre code.language-css .hljs-attribute) {
  color: #61afef;
}

.msg-content :deep(pre code.language-css .hljs-string),
.msg-content :deep(pre code.language-css .hljs-number) {
  color: #98c379;
}

/* Tool Action Buttons */
.tool-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.tool-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid var(--glass-border);
  background: rgba(255,255,255,0.03);
  color: var(--text-1);
}

.tool-action-btn:hover {
  background: rgba(255,255,255,0.08);
}

.tool-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.artifact-btn:hover {
  border-color: rgba(129,140,248,0.4);
  color: var(--accent);
}

.file-btn:hover {
  border-color: rgba(52,211,153,0.4);
  color: var(--emerald);
}

/* Artifact Table */
.artifact-table-container {
  margin-top: 12px;
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0,0,0,0.2);
}

.artifact-table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: rgba(255,255,255,0.03);
  border-bottom: 1px solid var(--glass-border);
}

.artifact-table-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-0);
}

.artifact-close-btn {
  background: none;
  border: none;
  color: var(--text-2);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 4px;
}

.artifact-close-btn:hover {
  background: rgba(255,255,255,0.1);
  color: var(--text-0);
}

.artifact-table-wrap {
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}

.artifact-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.artifact-table th {
  position: sticky;
  top: 0;
  background: rgba(0,0,0,0.4);
  padding: 8px 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-0);
  border-bottom: 1px solid var(--glass-border);
}

.artifact-table td {
  padding: 6px 12px;
  color: var(--text-1);
  border-bottom: 1px solid rgba(255,255,255,0.03);
}

.artifact-table tr:hover td {
  background: rgba(255,255,255,0.02);
}

.artifact-raw {
  padding: 12px 16px;
  max-height: 400px;
  overflow: auto;
}

.artifact-raw pre {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text-1);
  margin: 0;
  white-space: pre-wrap;
}

/* Sub-agent messages */
.sub-messages {
  margin-top: 8px;
  border-left: 2px solid var(--glass-border);
  padding-left: 12px;
}

.sub-messages-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--accent);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  padding: 4px 0;
  transition: color 0.2s ease;
}

.sub-messages-toggle:hover {
  color: var(--text-0);
}

.toggle-icon {
  transition: transform 0.2s ease;
}

.toggle-icon.expanded {
  transform: rotate(90deg);
}

.sub-messages-list {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sub-message {
  display: flex;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  background: color-mix(in srgb, var(--glass-bg) 50%, transparent);
}

.sub-message.user {
  background: color-mix(in srgb, var(--accent) 5%, transparent);
}

.sub-message.tool {
  background: color-mix(in srgb, #fbbf24 5%, transparent);
}

.sub-role {
  font-weight: 600;
  color: var(--text-1);
  white-space: nowrap;
  min-width: 36px;
}

.sub-message.user .sub-role { color: var(--accent); }
.sub-message.assistant .sub-role { color: var(--emerald); }
.sub-message.tool .sub-role { color: #fbbf24; }

.sub-content {
  color: var(--text-2);
  word-break: break-word;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>

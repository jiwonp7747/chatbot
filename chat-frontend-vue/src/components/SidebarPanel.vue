<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="brand">
        <div class="brand-icon">Bi</div>
        <div class="brand-text">Bistelligence</div>
      </div>
      <button class="new-chat-btn" @click="emit('new-chat')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        New Chat
      </button>
      <button class="mcp-tools-btn" @click="emit('mcp-tools-open')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M2 12h20"/><circle cx="12" cy="12" r="9"/></svg>
        MCP Tools
      </button>
      <button class="mcp-tools-btn" @click="emit('rag-tags-open')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
        RAG Tags
      </button>
    </div>

    <div class="chat-list">
      <div v-if="sessions.length === 0" class="empty-state">
        <p>채팅 내역이 없습니다</p>
      </div>
      <div
        v-else
        v-for="session in sessions"
        :key="session.id"
        :class="['chat-item', { active: currentSessionId === session.id }]"
        @click="onSessionSelect(session.id)"
      >
        <div class="chat-item-row">
          <template v-if="editingSessionId === session.id">
            <input
              ref="editInputRef"
              v-model="editingTitle"
              class="chat-title-input"
              type="text"
              maxlength="60"
              @click.stop
              @keydown.enter.stop.prevent="submitRename(session.id, session.title)"
              @keydown.esc.stop.prevent="cancelRename"
            />
            <div class="chat-item-actions editing">
              <button
                class="session-action-btn"
                type="button"
                aria-label="제목 저장"
                title="제목 저장"
                data-tooltip="저장"
                @click.stop="submitRename(session.id, session.title)"
              >
                ✓
              </button>
              <button
                class="session-action-btn"
                type="button"
                aria-label="수정 취소"
                title="수정 취소"
                data-tooltip="취소"
                @click.stop="cancelRename"
              >
                ↺
              </button>
            </div>
          </template>
          <template v-else>
            <div class="chat-item-title">{{ session.title }}</div>
            <div class="chat-item-actions">
              <button
                class="session-action-btn"
                type="button"
                aria-label="제목 변경"
                title="제목 변경"
                data-tooltip="제목 수정"
                @click.stop="startRenameSession(session.id, session.title)"
              >
                ✎
              </button>
              <button
                class="session-action-btn danger"
                type="button"
                aria-label="채팅 삭제"
                title="채팅 삭제"
                data-tooltip="채팅 삭제"
                @click.stop="onDeleteSession(session.id, session.title)"
              >
                ×
              </button>
            </div>
          </template>
        </div>
        <div class="chat-item-info">
          <span class="chat-item-date">{{ formatTimestamp(session.updatedAt) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue';
import type { ChatSession } from '../types/chat';

defineProps<{
  sessions: ChatSession[];
  currentSessionId: string | null;
}>();

const emit = defineEmits<{
  'session-select': [id: string];
  'new-chat': [];
  'mcp-tools-open': [];
  'rag-tags-open': [];
  'session-delete': [id: string];
  'session-rename': [payload: { id: string; title: string }];
}>();

const editingSessionId = ref<string | null>(null);
const editingTitle = ref('');
const editInputRef = ref<HTMLInputElement | null>(null);

function onSessionSelect(id: string) {
  if (editingSessionId.value) return;
  emit('session-select', id);
}

function onDeleteSession(id: string, title: string) {
  const ok = window.confirm(`'${title}' 채팅을 삭제할까요?`);
  if (!ok) return;
  emit('session-delete', id);
}

function startRenameSession(id: string, currentTitle: string) {
  editingSessionId.value = id;
  editingTitle.value = currentTitle;

  nextTick(() => {
    editInputRef.value?.focus();
    editInputRef.value?.select();
  });
}

function cancelRename() {
  editingSessionId.value = null;
  editingTitle.value = '';
}

function submitRename(id: string, currentTitle: string) {
  const trimmed = editingTitle.value.trim();
  if (!trimmed || trimmed === currentTitle) {
    cancelRename();
    return;
  }

  emit('session-rename', { id, title: trimmed });
  cancelRename();
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return '오늘';
  if (diffDays === 1) return '어제';
  if (diffDays < 7) return `${diffDays}일 전`;
  return date.toLocaleDateString('ko-KR');
}
</script>

<style scoped>
.sidebar {
  width: 300px;
  height: 100vh;
  background: var(--glass-bg);
  backdrop-filter: blur(40px) saturate(1.5);
  border-right: 1px solid var(--glass-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: var(--font);
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid var(--glass-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.brand-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--accent), #10b981);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: white;
}

.brand-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-0);
}

.new-chat-btn {
  width: 100%;
  padding: 12px 16px;
  background: var(--glass-bg);
  color: var(--text-1);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
}

.mcp-tools-btn {
  width: 100%;
  margin-top: 8px;
  padding: 10px 14px;
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--text-1);
  border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--glass-border));
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
}

.mcp-tools-btn:hover {
  background: color-mix(in srgb, var(--accent) 18%, transparent);
}

.new-chat-btn:hover {
  background: var(--glass-hover);
  border-color: rgba(255, 255, 255, 0.12);
}

.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.chat-list::-webkit-scrollbar {
  width: 4px;
}

.chat-list::-webkit-scrollbar-thumb {
  background: var(--glass-border);
  border-radius: 2px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-2);
  font-size: 13px;
}

.chat-item {
  padding: 12px 14px;
  margin-bottom: 8px;
  background: transparent;
  border-left: 2px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}

.chat-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.chat-item:hover {
  background: var(--glass-bg);
}

.chat-item.active {
  background: var(--accent-soft);
  border-left-color: rgba(129, 140, 248, 0.15);
}

.chat-item.active .chat-item-title {
  color: var(--accent);
}

.chat-item-title {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.chat-item-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0.8;
  transition: opacity 0.18s ease;
}

.chat-item-actions.editing {
  opacity: 1;
}

.chat-item:hover .chat-item-actions,
.chat-item.active .chat-item-actions {
  opacity: 1;
}

.chat-title-input {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--glass-border);
  background: var(--glass-bg);
  color: var(--text-0);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 13px;
  line-height: 1.3;
  outline: none;
}

.chat-title-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 20%, transparent);
}

.session-action-btn {
  position: relative;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-2);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  font-size: 12px;
  line-height: 1;
}

.session-action-btn::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  background: rgba(15, 23, 42, 0.95);
  color: #f8fafc;
  padding: 4px 7px;
  border-radius: 6px;
  font-size: 11px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
  z-index: 20;
}

.session-action-btn::before {
  content: '';
  position: absolute;
  bottom: calc(100% + 2px);
  left: 50%;
  transform: translateX(-50%) translateY(4px);
  border-width: 5px 4px 0 4px;
  border-style: solid;
  border-color: rgba(15, 23, 42, 0.95) transparent transparent transparent;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
  z-index: 20;
}

.session-action-btn:hover::after,
.session-action-btn:hover::before {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}

.session-action-btn:hover {
  background: var(--glass-hover);
  border-color: var(--glass-border);
  color: var(--text-1);
}

.session-action-btn.danger:hover {
  color: #ef4444;
}

.chat-item-info {
  display: flex;
  align-items: center;
  font-size: 11.5px;
  color: var(--text-2);
}
</style>

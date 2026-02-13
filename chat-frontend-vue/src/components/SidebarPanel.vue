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
        @click="emit('session-select', session.id)"
      >
        <div class="chat-item-title">{{ session.title }}</div>
        <div class="chat-item-info">
          <span class="chat-item-date">{{ formatTimestamp(session.updatedAt) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChatSession } from '../types/chat';

defineProps<{
  sessions: ChatSession[];
  currentSessionId: string | null;
}>();

const emit = defineEmits<{
  'session-select': [id: string];
  'new-chat': [];
}>();

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
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-item-info {
  display: flex;
  align-items: center;
  font-size: 11.5px;
  color: var(--text-2);
}
</style>

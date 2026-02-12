<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <h1 class="sidebar-title">Bistelligence AI</h1>
      <button class="new-chat-btn" @click="emit('new-chat')">
        <span class="new-chat-icon">+</span>
        새 채팅
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
  width: 280px;
  height: 100vh;
  background-color: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-primary);
}

.new-chat-btn {
  width: 100%;
  padding: 12px 16px;
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s ease;
}

.new-chat-btn:hover {
  background-color: var(--bg-hover);
  border-color: var(--text-tertiary);
}

.new-chat-icon {
  font-size: 18px;
  font-weight: 300;
}

.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-tertiary);
  font-size: 14px;
}

.chat-item {
  padding: 12px 16px;
  margin-bottom: 8px;
  background-color: var(--bg-secondary);
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.chat-item:hover {
  background-color: var(--bg-tertiary);
  border-color: var(--border-color);
}

.chat-item.active {
  background-color: var(--bg-tertiary);
  border-color: var(--accent-color);
}

.chat-item-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-item-info {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>

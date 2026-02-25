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
import { ref, watch, nextTick, onMounted } from 'vue';
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
  () => [props.session.messages, props.streamingContent],
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

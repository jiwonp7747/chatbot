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
      v-if="isStreaming && streamingContent"
      :message="{
        id: 'streaming',
        role: 'assistant',
        content: streamingContent,
        timestamp: Date.now()
      }"
    />
    <div ref="messagesEndRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue';
import ChatMessage from '../components/ChatMessage.vue';
import ModelSelector from '../components/ModelSelector.vue';
import type { ChatSession, ModelType } from '../types/chat';

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
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--bg-secondary);
}

.chat-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
  background-color: var(--bg-primary);
}

.messages-container::-webkit-scrollbar {
  width: 8px;
}

.messages-container::-webkit-scrollbar-track {
  background: var(--bg-primary);
}

.messages-container::-webkit-scrollbar-thumb {
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: var(--bg-hover);
}
</style>

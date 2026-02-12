<template>
  <form class="chat-input" @submit.prevent="handleSubmit">
    <div class="chat-input-container">
      <textarea
        ref="textareaRef"
        class="chat-input-field"
        v-model="message"
        @keydown="handleKeyDown"
        :placeholder="placeholder"
        :disabled="disabled"
        rows="1"
      />
      <button
        type="submit"
        class="chat-input-send"
        :disabled="!isStreaming && (!message.trim() || disabled)"
      >
        <svg
          v-if="isStreaming"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="currentColor"
          stroke="none"
        >
          <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
        <svg
          v-else
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
    <div class="chat-input-hint">
      <span>Enter로 전송, Shift+Enter로 줄바꿈</span>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

const props = withDefaults(defineProps<{
  disabled?: boolean;
  placeholder?: string;
  isStreaming?: boolean;
}>(), {
  disabled: false,
  placeholder: '메시지를 입력하세요...',
  isStreaming: false
});

const emit = defineEmits<{
  send: [message: string];
  stop: [];
}>();

const message = ref('');
const textareaRef = ref<HTMLTextAreaElement>();

watch(message, () => {
  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto';
      textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 200)}px`;
    }
  });
});

function handleSubmit() {
  if (props.isStreaming) {
    emit('stop');
  } else if (message.value.trim() && !props.disabled) {
    emit('send', message.value.trim());
    message.value = '';
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto';
    }
  }
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !props.isStreaming) {
    e.preventDefault();
    handleSubmit();
  }
}
</script>

<style scoped>
.chat-input {
  padding: 20px;
  background-color: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
}

.chat-input-container {
  position: relative;
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px 60px 12px 16px;
  transition: border-color 0.2s ease;
}

.chat-input-container:focus-within {
  border-color: var(--accent-color);
}

.chat-input-field {
  width: 100%;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 15px;
  font-family: inherit;
  resize: none;
  max-height: 200px;
  overflow-y: auto;
  line-height: 1.5;
}

.chat-input-field::placeholder {
  color: var(--text-tertiary);
}

.chat-input-field:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-input-send {
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background-color: var(--accent-color);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.chat-input-send:hover:not(:disabled) {
  background-color: var(--accent-hover);
  transform: scale(1.05);
}

.chat-input-send:disabled {
  background-color: var(--bg-hover);
  color: var(--text-tertiary);
  cursor: not-allowed;
  opacity: 0.5;
}

.chat-input-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
}
</style>

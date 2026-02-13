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
  padding: 16px 32px 24px;
  position: relative;
  z-index: 1;
}

.chat-input-container {
  max-width: 860px;
  margin: 0 auto;
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  padding: 12px 16px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.chat-input-container:focus-within {
  border-color: rgba(129, 140, 248, 0.3);
  box-shadow: 0 0 0 3px var(--accent-glow), 0 8px 32px rgba(0, 0, 0, 0.2);
}

.chat-input-field {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--text-0);
  font-family: var(--font);
  font-size: 14.5px;
  line-height: 1.5;
  resize: none;
  min-height: 24px;
  max-height: 120px;
}

.chat-input-field::placeholder {
  color: var(--text-2);
}

.chat-input-field:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-input-send {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--accent), var(--accent-hover));
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 12px var(--accent-glow);
}

.chat-input-send:hover:not(:disabled) {
  transform: scale(1.06);
  box-shadow: 0 4px 20px rgba(129, 140, 248, 0.3);
}

.chat-input-send:disabled {
  opacity: 0.3;
  cursor: default;
  transform: none;
  box-shadow: none;
}

.chat-input-hint {
  text-align: center;
  font-size: 11.5px;
  color: var(--text-2);
  margin-top: 10px;
  font-family: var(--mono);
  letter-spacing: 0.3px;
  max-width: 860px;
  margin-left: auto;
  margin-right: auto;
}
</style>

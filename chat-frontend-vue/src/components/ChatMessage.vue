<template>
  <div :class="['chat-message', message.role]">
    <div class="message-avatar">
      {{ message.role === 'user' ? '👤' : '🤖' }}
    </div>
    <div class="message-content">
      <div class="message-role">
        {{ message.role === 'user' ? 'You' : 'AI' }}
      </div>
      <div class="message-text" v-html="renderedContent" />
      <div class="message-timestamp">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useMarkdown } from '../composables/useMarkdown';
import type { Message } from '../types/chat';

const props = defineProps<{
  message: Message;
}>();

const { renderMarkdown } = useMarkdown();

const renderedContent = computed(() => renderMarkdown(props.message.content));

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit'
  });
}
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 16px;
  padding: 24px;
  margin-bottom: 16px;
}

.chat-message.user {
  background-color: var(--bg-secondary);
}

.chat-message.assistant {
  background-color: var(--bg-primary);
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.message-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
  word-wrap: break-word;
}

.message-timestamp {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 8px;
}

/* Markdown styling */
.message-text :deep(p) {
  margin: 0 0 12px 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(h1),
.message-text :deep(h2),
.message-text :deep(h3),
.message-text :deep(h4),
.message-text :deep(h5),
.message-text :deep(h6) {
  margin: 16px 0 8px 0;
  font-weight: 600;
  line-height: 1.4;
}

.message-text :deep(h1) { font-size: 24px; }
.message-text :deep(h2) { font-size: 20px; }
.message-text :deep(h3) { font-size: 18px; }
.message-text :deep(h4) { font-size: 16px; }

.message-text :deep(ul),
.message-text :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.message-text :deep(li) {
  margin: 4px 0;
}

.message-text :deep(code) {
  background-color: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
}

.message-text :deep(pre) {
  background-color: var(--bg-tertiary);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
  margin: 12px 0;
}

.message-text :deep(pre code) {
  background-color: transparent;
  padding: 0;
  font-size: 14px;
  line-height: 1.5;
}

.message-text :deep(a) {
  color: #0969da;
  text-decoration: none;
}

.message-text :deep(a:hover) {
  text-decoration: underline;
}

.message-text :deep(blockquote) {
  border-left: 4px solid var(--border-color);
  padding-left: 16px;
  margin: 12px 0;
  color: var(--text-secondary);
}

.message-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
}

.message-text :deep(th),
.message-text :deep(td) {
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  text-align: left;
}

.message-text :deep(th) {
  background-color: var(--bg-tertiary);
  font-weight: 600;
}

.message-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 16px 0;
}

.message-text :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 12px 0;
}

/* Code block custom styles */
.message-text :deep(pre code.hljs) {
  background-color: #282c34;
  color: #abb2bf;
  padding: 16px;
  border-radius: 8px;
}

/* YAML */
.message-text :deep(pre code.language-yaml .hljs-attr),
.message-text :deep(pre code.language-yml .hljs-attr) {
  color: #e06c75 !important;
}

.message-text :deep(pre code.language-yaml .hljs-string),
.message-text :deep(pre code.language-yml .hljs-string) {
  color: #98c379 !important;
}

.message-text :deep(pre code.language-yaml .hljs-number),
.message-text :deep(pre code.language-yml .hljs-number) {
  color: #98c379 !important;
}

.message-text :deep(pre code.language-yaml .hljs-literal),
.message-text :deep(pre code.language-yml .hljs-literal) {
  color: #98c379 !important;
}

/* Text, Bash, Shell */
.message-text :deep(pre code.language-text),
.message-text :deep(pre code.language-bash),
.message-text :deep(pre code.language-sh),
.message-text :deep(pre code.language-shell),
.message-text :deep(pre code.language-plaintext) {
  color: #e6e6e6 !important;
}

.message-text :deep(pre code.language-text *),
.message-text :deep(pre code.language-bash *),
.message-text :deep(pre code.language-sh *),
.message-text :deep(pre code.language-shell *),
.message-text :deep(pre code.language-plaintext *) {
  color: #e6e6e6 !important;
}

/* JavaScript/TypeScript */
.message-text :deep(pre code.language-javascript .hljs-keyword),
.message-text :deep(pre code.language-typescript .hljs-keyword),
.message-text :deep(pre code.language-js .hljs-keyword),
.message-text :deep(pre code.language-ts .hljs-keyword) {
  color: #c678dd;
}

.message-text :deep(pre code.language-javascript .hljs-function),
.message-text :deep(pre code.language-typescript .hljs-function),
.message-text :deep(pre code.language-js .hljs-function),
.message-text :deep(pre code.language-ts .hljs-function) {
  color: #61afef;
}

.message-text :deep(pre code.language-javascript .hljs-string),
.message-text :deep(pre code.language-typescript .hljs-string),
.message-text :deep(pre code.language-js .hljs-string),
.message-text :deep(pre code.language-ts .hljs-string) {
  color: #98c379;
}

.message-text :deep(pre code.language-javascript .hljs-number),
.message-text :deep(pre code.language-typescript .hljs-number),
.message-text :deep(pre code.language-js .hljs-number),
.message-text :deep(pre code.language-ts .hljs-number) {
  color: #d19a66;
}

/* Python */
.message-text :deep(pre code.language-python .hljs-keyword) {
  color: #c678dd;
}

.message-text :deep(pre code.language-python .hljs-string) {
  color: #98c379;
}

.message-text :deep(pre code.language-python .hljs-number) {
  color: #d19a66;
}

.message-text :deep(pre code.language-python .hljs-function) {
  color: #61afef;
}

/* JSON */
.message-text :deep(pre code.language-json .hljs-attr) {
  color: #e06c75;
}

.message-text :deep(pre code.language-json .hljs-string) {
  color: #98c379;
}

.message-text :deep(pre code.language-json .hljs-number),
.message-text :deep(pre code.language-json .hljs-literal) {
  color: #d19a66;
}

/* HTML/CSS */
.message-text :deep(pre code.language-html .hljs-tag),
.message-text :deep(pre code.language-xml .hljs-tag) {
  color: #e06c75;
}

.message-text :deep(pre code.language-html .hljs-name),
.message-text :deep(pre code.language-xml .hljs-name) {
  color: #e06c75;
}

.message-text :deep(pre code.language-html .hljs-attr),
.message-text :deep(pre code.language-xml .hljs-attr) {
  color: #d19a66;
}

.message-text :deep(pre code.language-css .hljs-selector-tag),
.message-text :deep(pre code.language-css .hljs-selector-class),
.message-text :deep(pre code.language-css .hljs-selector-id) {
  color: #e06c75;
}

.message-text :deep(pre code.language-css .hljs-attribute) {
  color: #61afef;
}

.message-text :deep(pre code.language-css .hljs-string),
.message-text :deep(pre code.language-css .hljs-number) {
  color: #98c379;
}
</style>

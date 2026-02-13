<template>
  <div :class="['message', message.role]">
    <div class="msg-avatar">
      {{ message.role === 'user' ? avatarInitial : 'Bi' }}
    </div>
    <div class="msg-body">
      <div class="msg-meta">
        <span class="msg-name">{{ message.role === 'user' ? 'You' : 'Bistelligence' }}</span>
        <span class="msg-time">{{ formatTime(message.timestamp) }}</span>
      </div>
      <div class="msg-content" v-html="renderedContent" />
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

const avatarInitial = 'J';

const renderedContent = computed(() => renderMarkdown(props.message.content));

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
</style>

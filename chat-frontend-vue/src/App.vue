<template>
  <div class="app">
    <!-- Ambient background -->
    <div class="ambient">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
    </div>

    <SidebarPanel
      :sessions="store.sessions"
      :current-session-id="store.currentSessionId"
      :collapsed="sidebarCollapsed"
      @session-select="store.selectSession"
      @new-chat="store.newChat"
      @mcp-tools-open="openMcpToolsPanel"
      @rag-tags-open="openRagTagsPanel"
      @session-delete="handleSessionDelete"
      @session-rename="handleSessionRename"
      @toggle-sidebar="toggleSidebar"
    />
    <div class="main-content">
      <button
        v-if="sidebarCollapsed"
        class="sidebar-expand-btn"
        aria-label="사이드바 펼치기"
        @click="toggleSidebar"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
      <WelcomePage
        v-if="!store.currentSession"
        :selected-model="store.selectedModel"
        @model-change="(model) => store.selectedModel = model"
      />
      <ChatPage
        v-else
        :key="store.currentSession.id"
        :session="store.currentSession"
        :streaming-content="store.currentStreamingContent"
        :is-streaming="store.isStreaming"
        @model-change="store.updateSessionModel"
      />
      <ChatInput
        :is-streaming="store.isStreaming"
        :disabled="false"
        :placeholder="store.isStreaming ? '응답을 기다리는 중...' : 'Ask anything...'"
        @send="store.sendMessage"
        @stop="store.stopStreaming"
      />
    </div>

    <McpToolsPanel
      :open="isMcpPanelOpen"
      :tools="mcpTools"
      :loading="isMcpToolsLoading"
      :error="mcpToolsError"
      @close="isMcpPanelOpen = false"
      @retry="loadMcpTools"
    />
    <RagTagsPanel
      :open="isRagPanelOpen"
      :tags="ragTags"
      :loading="isRagTagsLoading"
      :error="ragTagsError"
      @close="isRagPanelOpen = false"
      @retry="loadRagTags"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useChatStore } from './stores/chatStore';
import SidebarPanel from './components/SidebarPanel.vue';
import ChatInput from './components/ChatInput.vue';
import WelcomePage from './pages/WelcomePage.vue';
import ChatPage from './pages/ChatPage.vue';
import McpToolsPanel from './components/McpToolsPanel.vue';
import RagTagsPanel from './components/RagTagsPanel.vue';
import { chatService } from './services/chatService';
import type { McpTool, TagTreeNode } from './types/chat';

const sidebarCollapsed = ref(false);

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

const store = useChatStore();
const isMcpPanelOpen = ref(false);
const isMcpToolsLoading = ref(false);
const mcpToolsError = ref<string | null>(null);
const mcpTools = ref<McpTool[]>([]);

const isRagPanelOpen = ref(false);
const isRagTagsLoading = ref(false);
const ragTagsError = ref<string | null>(null);
const ragTags = ref<TagTreeNode[]>([]);

onMounted(() => {
  store.loadSessions();
});

async function handleSessionDelete(sessionId: string) {
  try {
    await store.deleteSession(sessionId);
  } catch (error) {
    console.error('세션 삭제 실패:', error);
    window.alert('세션 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.');
  }
}

async function handleSessionRename(payload: { id: string; title: string }) {
  try {
    await store.renameSession(payload.id, payload.title);
  } catch (error) {
    console.error('세션 제목 변경 실패:', error);
    window.alert('세션 제목 변경에 실패했습니다. 잠시 후 다시 시도해주세요.');
  }
}

async function loadMcpTools() {
  isMcpToolsLoading.value = true;
  mcpToolsError.value = null;

  try {
    mcpTools.value = await chatService.fetchMcpTools();
  } catch (error) {
    console.error('MCP 도구 목록 조회 실패:', error);
    mcpToolsError.value = 'MCP 도구 목록을 불러오지 못했습니다.';
  } finally {
    isMcpToolsLoading.value = false;
  }
}

async function loadRagTags() {
  isRagTagsLoading.value = true;
  ragTagsError.value = null;

  try {
    ragTags.value = await chatService.fetchRagTags();
  } catch (error) {
    console.error('RAG 태그 목록 조회 실패:', error);
    ragTagsError.value = 'RAG 태그 목록을 불러오지 못했습니다.';
  } finally {
    isRagTagsLoading.value = false;
  }
}

function openMcpToolsPanel() {
  isMcpPanelOpen.value = true;
  if (mcpTools.value.length === 0 && !isMcpToolsLoading.value) {
    loadMcpTools();
  }
}

function openRagTagsPanel() {
  isRagPanelOpen.value = true;
  if (ragTags.value.length === 0 && !isRagTagsLoading.value) {
    loadRagTags();
  }
}
</script>

<style scoped>
.app {
  position: relative;
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: var(--surface-0);
}

.ambient {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none;
}

.ambient .orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.35;
  animation: drift 20s ease-in-out infinite alternate;
}

.ambient .orb-1 {
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, var(--accent) 0%, transparent 70%);
  top: -200px;
  left: -100px;
}

.ambient .orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, var(--emerald) 0%, transparent 70%);
  bottom: -200px;
  right: -100px;
  animation-delay: -10s;
}

.ambient .orb-3 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, #f472b6 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  opacity: 0.15;
  animation-delay: -5s;
}

@keyframes drift {
  0% { transform: translate(0, 0) scale(1); }
  100% { transform: translate(40px, -30px) scale(1.1); }
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.sidebar-expand-btn {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 10;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  color: var(--text-1);
  cursor: pointer;
  backdrop-filter: blur(12px);
  transition: background 0.2s ease, border-color 0.2s ease;
}

.sidebar-expand-btn:hover {
  background: var(--glass-hover);
  border-color: rgba(255, 255, 255, 0.12);
}
</style>

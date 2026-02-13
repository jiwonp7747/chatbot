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
      @session-select="store.selectSession"
      @new-chat="store.newChat"
      @session-delete="handleSessionDelete"
      @session-rename="handleSessionRename"
    />
    <div class="main-content">
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
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useChatStore } from './stores/chatStore';
import SidebarPanel from './components/SidebarPanel.vue';
import ChatInput from './components/ChatInput.vue';
import WelcomePage from './pages/WelcomePage.vue';
import ChatPage from './pages/ChatPage.vue';

const store = useChatStore();

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
</style>

<template>
  <div class="app">
    <SidebarPanel
      :sessions="store.sessions"
      :current-session-id="store.currentSessionId"
      @session-select="store.selectSession"
      @new-chat="store.newChat"
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
        :placeholder="store.isStreaming ? '응답을 기다리는 중...' : '메시지를 입력하세요...'"
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
</script>

<style scoped>
.app {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background-color: var(--bg-primary);
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}
</style>

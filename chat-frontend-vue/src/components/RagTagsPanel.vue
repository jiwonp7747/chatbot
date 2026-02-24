<template>
  <div v-if="open" class="rag-overlay" @click.self="emit('close')">
    <div class="rag-panel" role="dialog" aria-modal="true" aria-label="RAG 태그 선택">
      <div class="rag-header">
        <div>
          <h3>RAG Tags</h3>
          <p>검색에 사용할 태그를 선택하세요. 선택된 태그의 메모리에서 관련 정보를 검색합니다.</p>
        </div>
        <button class="icon-btn" type="button" @click="emit('close')">✕</button>
      </div>

      <div class="rag-body">
        <div v-if="loading" class="state">불러오는 중...</div>
        <div v-else-if="error" class="state error">
          <p>{{ error }}</p>
          <button class="retry-btn" type="button" @click="emit('retry')">다시 시도</button>
        </div>
        <div v-else-if="tags.length === 0" class="state">사용 가능한 태그가 없습니다.</div>
        <template v-else>
          <div class="tag-actions">
            <span class="tag-count">{{ selectedTags.length }}개 선택됨</span>
            <button v-if="selectedTags.length > 0" class="clear-btn" type="button" @click="clearAll">
              전체 해제
            </button>
          </div>
          <div class="tag-grid">
            <button
              v-for="tag in tags"
              :key="tag"
              class="tag-chip"
              :class="{ selected: isSelected(tag) }"
              type="button"
              @click="toggleTag(tag)"
            >
              {{ tag }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useChatStore } from '../stores/chatStore';

const props = defineProps<{
  open: boolean;
  tags: string[];
  loading: boolean;
  error: string | null;
}>();

const emit = defineEmits<{
  close: [];
  retry: [];
}>();

const store = useChatStore();

const selectedTags = computed(() => store.selectedRagTags);

function isSelected(tag: string): boolean {
  return selectedTags.value.includes(tag);
}

function toggleTag(tag: string) {
  const index = store.selectedRagTags.indexOf(tag);
  if (index > -1) {
    store.selectedRagTags.splice(index, 1);
  } else {
    store.selectedRagTags.push(tag);
  }
}

function clearAll() {
  store.selectedRagTags = [];
}
</script>

<style scoped>
.rag-overlay {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.55);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  z-index: 100;
}

.rag-panel {
  width: min(560px, calc(100vw - 40px));
  max-height: min(600px, calc(100vh - 40px));
  background: #0b1220;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.rag-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.rag-header h3 {
  margin: 0;
  font-size: 18px;
}

.rag-header p {
  margin: 4px 0 0;
  color: #94a3b8;
  font-size: 12px;
}

.icon-btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: transparent;
  color: #cbd5e1;
  border-radius: 8px;
  width: 30px;
  height: 30px;
  cursor: pointer;
}

.rag-body {
  flex: 1;
  overflow: auto;
  padding: 16px 18px;
}

.tag-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.tag-count {
  font-size: 13px;
  color: #94a3b8;
}

.clear-btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: transparent;
  color: #94a3b8;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.clear-btn:hover {
  color: #e2e8f0;
  border-color: rgba(148, 163, 184, 0.4);
}

.tag-grid {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag-chip {
  padding: 6px 14px;
  background: rgba(15, 23, 42, 0.6);
  color: #cbd5e1;
  font-size: 13px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  cursor: pointer;
  transition: all 0.2s ease;
  font-weight: 500;
}

.tag-chip:hover {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(148, 163, 184, 0.4);
}

.tag-chip.selected {
  background: rgba(129, 140, 248, 0.2);
  color: #a5b4fc;
  border-color: rgba(129, 140, 248, 0.5);
}

.state {
  color: #94a3b8;
  font-size: 13px;
  padding: 12px;
}

.state.error p {
  margin: 0 0 8px;
  color: #fecaca;
}

.retry-btn {
  border: 1px solid rgba(248, 113, 113, 0.6);
  color: #fecaca;
  background: transparent;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
}

@media (max-width: 600px) {
  .rag-panel {
    width: calc(100vw - 20px);
    max-height: calc(100vh - 20px);
  }
}
</style>

<template>
  <div v-if="open" class="rag-overlay" @click.self="emit('close')">
    <div class="rag-panel" role="dialog" aria-modal="true" aria-label="RAG 태그 선택">
      <div class="rag-header">
        <div>
          <h3>RAG Tags</h3>
          <p>검색에 사용할 태그를 선택하세요. 상위 태그 선택 시 하위 태그도 함께 선택됩니다.</p>
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
            <span class="tag-count">{{ store.selectedRagTags.length }}개 선택됨</span>
            <button v-if="store.selectedRagTags.length > 0" class="clear-btn" type="button" @click="clearAll">
              전체 해제
            </button>
          </div>
          <div class="tag-tree">
            <TagTreeItem
              v-for="node in tags"
              :key="node.id"
              :node="node"
              :selected-tags="store.selectedRagTags"
              @toggle="toggleTagWithChildren"
            />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useChatStore } from '../stores/chatStore';
import type { TagTreeNode } from '../types/chat';
import TagTreeItem from './TagTreeItem.vue';

defineProps<{
  open: boolean;
  tags: TagTreeNode[];
  loading: boolean;
  error: string | null;
}>();

const emit = defineEmits<{
  close: [];
  retry: [];
}>();

const store = useChatStore();

function collectDescendantNames(node: TagTreeNode): string[] {
  const names: string[] = [];
  for (const child of node.children ?? []) {
    names.push(child.name);
    names.push(...collectDescendantNames(child));
  }
  return names;
}

function toggleTagWithChildren(node: TagTreeNode) {
  const isSelected = store.selectedRagTags.includes(node.name);

  if (isSelected) {
    const toRemove = new Set([node.name, ...collectDescendantNames(node)]);
    store.selectedRagTags = store.selectedRagTags.filter(t => !toRemove.has(t));
  } else {
    const allNames = [node.name, ...collectDescendantNames(node)];
    const toAdd = allNames.filter(n => !store.selectedRagTags.includes(n));
    store.selectedRagTags.push(...toAdd);
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
  width: min(520px, calc(100vw - 40px));
  max-height: min(640px, calc(100vh - 40px));
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

.tag-tree {
  display: flex;
  flex-direction: column;
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

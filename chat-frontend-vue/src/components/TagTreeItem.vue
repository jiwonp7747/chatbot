<template>
  <div class="tree-node">
    <div class="tree-row" @click="emit('toggle', node)">
      <span class="tree-indent" :style="{ width: node.level * 20 + 'px' }" />
      <span v-if="node.children?.length" class="tree-arrow" :class="{ expanded }">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </span>
      <span v-else class="tree-arrow-placeholder" />
      <input
        type="checkbox"
        class="tree-checkbox"
        :checked="isSelected"
        @click.stop="emit('toggle', node)"
      />
      <span class="tree-label">{{ node.name }}</span>
      <span class="tree-count">{{ totalFileCount }}</span>
    </div>
    <div v-if="expanded && node.children?.length" class="tree-children">
      <TagTreeItem
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :selected-tags="selectedTags"
        @toggle="(n) => emit('toggle', n)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { TagTreeNode } from '../types/chat';

const props = defineProps<{
  node: TagTreeNode;
  selectedTags: string[];
}>();

const emit = defineEmits<{
  toggle: [node: TagTreeNode];
}>();

const expanded = ref(true);

const isSelected = computed(() => props.selectedTags.includes(props.node.name));

const totalFileCount = computed(() => getTotalFileCount(props.node));

function getTotalFileCount(node: TagTreeNode): number {
  let total = node.file_count;
  for (const child of node.children ?? []) {
    total += getTotalFileCount(child);
  }
  return total;
}
</script>

<style scoped>
.tree-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.tree-row:hover {
  background: rgba(30, 41, 59, 0.6);
}

.tree-indent {
  flex-shrink: 0;
}

.tree-arrow {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  transition: transform 0.2s ease;
}

.tree-arrow.expanded {
  transform: rotate(90deg);
}

.tree-arrow-placeholder {
  flex-shrink: 0;
  width: 16px;
}

.tree-checkbox {
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  accent-color: #818cf8;
  cursor: pointer;
}

.tree-label {
  flex: 1;
  font-size: 13px;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-count {
  flex-shrink: 0;
  font-size: 11px;
  color: #64748b;
  padding: 1px 6px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 4px;
}
</style>

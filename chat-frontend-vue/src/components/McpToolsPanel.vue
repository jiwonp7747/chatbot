<template>
  <div v-if="open" class="mcp-overlay" @click.self="emit('close')">
    <div class="mcp-panel" role="dialog" aria-modal="true" aria-label="MCP 도구 목록">
      <div class="mcp-header">
        <div>
          <h3>MCP Tools</h3>
          <p>사용 가능한 MCP 도구를 검색하고 스키마를 확인할 수 있습니다.</p>
        </div>
        <button class="icon-btn" type="button" @click="emit('close')">✕</button>
      </div>

      <div class="mcp-controls">
        <input
          v-model="searchQuery"
          type="text"
          class="control-input"
          placeholder="도구명/설명 검색"
        />
        <select v-model="selectedCategory" class="control-select">
          <option value="all">모든 카테고리</option>
          <option v-for="category in categories" :key="category" :value="category">
            {{ category }}
          </option>
        </select>
        <select v-model="sortMode" class="control-select">
          <option value="recent">최근 사용순</option>
          <option value="name">이름순</option>
          <option value="mcp">MCP 서버순</option>
        </select>
      </div>

      <div class="mcp-body">
        <div class="tool-list">
          <div v-if="loading" class="state">불러오는 중...</div>
          <div v-else-if="error" class="state error">
            <p>{{ error }}</p>
            <button class="retry-btn" type="button" @click="emit('retry')">다시 시도</button>
          </div>
          <div v-else-if="filteredTools.length === 0" class="state">조건에 맞는 도구가 없습니다.</div>
          <button
            v-for="tool in filteredTools"
            :key="tool.id"
            class="tool-item"
            :class="{ active: selectedToolId === tool.id }"
            type="button"
            @click="selectTool(tool)"
          >
            <div class="tool-head">
              <strong>{{ tool.tool_name }}</strong>
              <span class="badge">{{ tool.category }}</span>
            </div>
            <div class="tool-sub">{{ tool.mcp_name }}</div>
            <div class="tool-desc">{{ tool.description || '설명 없음' }}</div>
          </button>
        </div>

        <div class="tool-detail">
          <template v-if="selectedTool">
            <h4>{{ selectedTool.tool_name }}</h4>
            <div class="detail-line"><b>MCP</b> {{ selectedTool.mcp_name }}</div>
            <div class="detail-line"><b>카테고리</b> {{ selectedTool.category }}</div>
            <div class="detail-line"><b>상태</b> {{ selectedTool.available ? 'available' : 'unavailable' }}</div>
            <div class="detail-line"><b>필드</b> {{ selectedTool.input_schema_preview.fields.join(', ') || '-' }}</div>
            <div class="detail-line"><b>필수</b> {{ selectedTool.input_schema_preview.required.join(', ') || '-' }}</div>

            <div class="schema-block">
              <div class="schema-title">Input Schema</div>
              <pre>{{ prettySchema(selectedTool.input_schema) }}</pre>
            </div>
          </template>
          <div v-else class="state">좌측에서 도구를 선택하세요.</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { McpTool } from '../types/chat';

const props = defineProps<{
  open: boolean;
  tools: McpTool[];
  loading: boolean;
  error: string | null;
}>();

const emit = defineEmits<{
  close: [];
  retry: [];
}>();

const RECENT_KEY = 'mcp_recent_tools';
const searchQuery = ref('');
const selectedCategory = ref('all');
const sortMode = ref<'recent' | 'name' | 'mcp'>('recent');
const selectedToolId = ref<string | null>(null);
const recentMap = ref<Record<string, number>>({});

const categories = computed(() => {
  return [...new Set(props.tools.map(tool => tool.category))].sort((a, b) => a.localeCompare(b));
});

const selectedTool = computed(() => {
  if (!selectedToolId.value) return null;
  return props.tools.find(tool => tool.id === selectedToolId.value) || null;
});

function getRecentMap(): Record<string, number> {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === 'object' && parsed ? parsed : {};
  } catch {
    return {};
  }
}

recentMap.value = getRecentMap();

function saveRecentMap(next: Record<string, number>) {
  localStorage.setItem(RECENT_KEY, JSON.stringify(next));
}

function selectTool(tool: McpTool) {
  selectedToolId.value = tool.id;
  const nextRecent = {
    ...recentMap.value,
    [tool.id]: Date.now(),
  };
  recentMap.value = nextRecent;
  saveRecentMap(nextRecent);
}

const filteredTools = computed(() => {
  const query = searchQuery.value.trim().toLowerCase();
  const recent = recentMap.value;

  const filtered = props.tools.filter(tool => {
    if (selectedCategory.value !== 'all' && tool.category !== selectedCategory.value) {
      return false;
    }
    if (!query) return true;

    const target = `${tool.tool_name} ${tool.description} ${tool.mcp_name}`.toLowerCase();
    return target.includes(query);
  });

  return filtered.sort((a, b) => {
    if (sortMode.value === 'name') {
      return a.tool_name.localeCompare(b.tool_name);
    }
    if (sortMode.value === 'mcp') {
      return `${a.mcp_name}:${a.tool_name}`.localeCompare(`${b.mcp_name}:${b.tool_name}`);
    }
    return (recent[b.id] || 0) - (recent[a.id] || 0);
  });
});

function prettySchema(schema: Record<string, unknown>): string {
  return JSON.stringify(schema || {}, null, 2);
}
</script>

<style scoped>
.mcp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(2, 6, 23, 0.55);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  z-index: 100;
}

.mcp-panel {
  width: min(1050px, calc(100vw - 40px));
  height: min(760px, calc(100vh - 40px));
  background: #0b1220;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mcp-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.mcp-header h3 {
  margin: 0;
  font-size: 18px;
}

.mcp-header p {
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

.mcp-controls {
  padding: 12px 18px;
  display: grid;
  grid-template-columns: 1.7fr 1fr 1fr;
  gap: 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.control-input,
.control-select {
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
  color: #e2e8f0;
  padding: 8px 10px;
}

.mcp-body {
  flex: 1;
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  min-height: 0;
}

.tool-list {
  border-right: 1px solid rgba(148, 163, 184, 0.2);
  overflow: auto;
  padding: 10px;
}

.tool-detail {
  overflow: auto;
  padding: 14px;
}

.tool-item {
  width: 100%;
  text-align: left;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.45);
  color: inherit;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 8px;
  cursor: pointer;
}

.tool-item.active {
  border-color: rgba(56, 189, 248, 0.7);
  background: rgba(30, 64, 175, 0.2);
}

.tool-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.badge {
  font-size: 11px;
  color: #a5f3fc;
  border: 1px solid rgba(34, 211, 238, 0.45);
  border-radius: 999px;
  padding: 2px 7px;
}

.tool-sub {
  margin-top: 2px;
  color: #93c5fd;
  font-size: 12px;
}

.tool-desc {
  margin-top: 6px;
  color: #cbd5e1;
  font-size: 12px;
}

.detail-line {
  margin-top: 8px;
  font-size: 13px;
  color: #cbd5e1;
}

.detail-line b {
  margin-right: 6px;
  color: #f8fafc;
}

.schema-block {
  margin-top: 14px;
}

.schema-title {
  color: #f8fafc;
  font-size: 13px;
  margin-bottom: 8px;
}

.schema-block pre {
  margin: 0;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  padding: 10px;
  font-size: 11.5px;
  line-height: 1.45;
  overflow: auto;
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

@media (max-width: 900px) {
  .mcp-panel {
    width: calc(100vw - 20px);
    height: calc(100vh - 20px);
  }

  .mcp-controls {
    grid-template-columns: 1fr;
  }

  .mcp-body {
    grid-template-columns: 1fr;
  }

  .tool-list {
    border-right: 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  }
}
</style>

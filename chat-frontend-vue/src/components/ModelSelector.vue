<template>
  <div class="model-selector" ref="dropdownRef">
    <button
      class="model-selector-btn"
      @click="isOpen = !isOpen"
      :disabled="isLoading || error !== null || models.length === 0"
    >
      <span class="model-selector-label">
        {{ isLoading ? '로딩 중...' : error ? '오류 발생' : selectedModelInfo?.label || '모델 선택' }}
      </span>
      <span :class="['model-selector-arrow', { open: isOpen }]">▼</span>
    </button>

    <div v-if="isOpen && !isLoading && !error && models.length > 0" class="model-selector-dropdown">
      <div
        v-for="model in models"
        :key="model.value"
        :class="['model-option', { selected: selectedModel === model.value }]"
        @click="handleModelSelect(model.value)"
      >
        <div class="model-option-label">{{ model.label }}</div>
        <div class="model-option-description">{{ model.description }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { ModelType } from '../types/chat';
import { getAvailAbleModelListUrl } from '../config/api';

interface ApiModelData {
  model_name: string;
  model_type: string;
  model_id: number;
  summary: string;
}

interface ApiResponse {
  success: boolean;
  message: string;
  data: ApiModelData[];
  status_code: number;
}

interface Model {
  value: ModelType;
  label: string;
  description: string;
  model_id: number;
}

const props = defineProps<{
  selectedModel: ModelType;
}>();

const emit = defineEmits<{
  'model-change': [model: ModelType];
}>();

const isOpen = ref(false);
const models = ref<Model[]>([]);
const isLoading = ref(true);
const error = ref<string | null>(null);
const dropdownRef = ref<HTMLDivElement>();

const selectedModelInfo = computed(() =>
  models.value.find(m => m.value === props.selectedModel) || models.value[0]
);

onMounted(async () => {
  try {
    isLoading.value = true;
    error.value = null;
    const response = await fetch(getAvailAbleModelListUrl());

    if (!response.ok) {
      throw new Error('모델 목록을 불러오는데 실패했습니다.');
    }

    const apiResponse: ApiResponse = await response.json();

    if (apiResponse.success && apiResponse.data) {
      models.value = apiResponse.data.map((item) => ({
        value: item.model_type as ModelType,
        label: item.model_name,
        description: item.summary,
        model_id: item.model_id
      }));
    } else {
      throw new Error(apiResponse.message || '모델 목록을 불러오는데 실패했습니다.');
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.';
    console.error('Failed to fetch models:', err);
  } finally {
    isLoading.value = false;
  }

  document.addEventListener('mousedown', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('mousedown', handleClickOutside);
});

function handleClickOutside(event: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target as Node)) {
    isOpen.value = false;
  }
}

function handleModelSelect(model: ModelType) {
  emit('model-change', model);
  isOpen.value = false;
}
</script>

<style scoped>
.model-selector {
  position: relative;
}

.model-selector-btn {
  padding: 8px 16px;
  background-color: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.2s ease;
  min-width: 160px;
}

.model-selector-btn:hover {
  background-color: var(--bg-hover);
  border-color: var(--text-tertiary);
}

.model-selector-label {
  font-weight: 500;
}

.model-selector-arrow {
  font-size: 10px;
  transition: transform 0.2s ease;
  color: var(--text-secondary);
}

.model-selector-arrow.open {
  transform: rotate(180deg);
}

.model-selector-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background-color: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  overflow: hidden;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.model-option {
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s ease;
  border-bottom: 1px solid var(--border-color);
}

.model-option:last-child {
  border-bottom: none;
}

.model-option:hover {
  background-color: var(--bg-hover);
}

.model-option.selected {
  background-color: var(--bg-hover);
}

.model-option.selected::before {
  content: '✓ ';
  color: var(--accent-color);
  font-weight: bold;
}

.model-option-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.model-option-description {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>

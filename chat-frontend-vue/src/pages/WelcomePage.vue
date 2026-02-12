<template>
  <div class="welcome-screen">
    <div class="welcome-content">
      <h1 class="welcome-title">Bistelligence AI</h1>
      <p class="welcome-subtitle">무엇을 도와드릴까요?</p>
      <div class="model-selector-wrapper">
        <ModelSelector
          :selected-model="selectedModel"
          @model-change="emit('model-change', $event)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import ModelSelector from '../components/ModelSelector.vue';
import type { ModelType } from '../types/chat';

defineProps<{
  selectedModel: ModelType;
}>();

const emit = defineEmits<{
  'model-change': [model: ModelType];
}>();
</script>

<style scoped>
.welcome-screen {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-primary);
}

.welcome-content {
  text-align: center;
  max-width: 600px;
  padding: 40px;
}

.welcome-title {
  font-size: 48px;
  font-weight: 700;
  margin-bottom: 16px;
  background: linear-gradient(135deg, var(--accent-color), var(--success-color));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-subtitle {
  font-size: 20px;
  color: var(--text-secondary);
  margin-bottom: 40px;
}

.model-selector-wrapper {
  display: flex;
  justify-content: center;
}
</style>

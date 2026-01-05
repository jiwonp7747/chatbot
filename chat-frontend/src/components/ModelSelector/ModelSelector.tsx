import React, { useState, useRef, useEffect } from 'react';
import './ModelSelector.css';
import { ModelType } from '../../types/chat';
import { getAvailAbleModelListUrl } from '../../config/api';

interface ModelSelectorProps {
  selectedModel: ModelType;
  onModelChange: (model: ModelType) => void;
}

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

const ModelSelector: React.FC<ModelSelectorProps> = ({ selectedModel, onModelChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [models, setModels] = useState<Model[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const response = await fetch(getAvailAbleModelListUrl());

        if (!response.ok) {
          throw new Error('모델 목록을 불러오는데 실패했습니다.');
        }

        const apiResponse: ApiResponse = await response.json();

        if (apiResponse.success && apiResponse.data) {
          const modelList: Model[] = apiResponse.data.map((item) => ({
            value: item.model_type as ModelType,
            label: item.model_name,
            description: item.summary,
            model_id: item.model_id
          }));
          setModels(modelList);
        } else {
          throw new Error(apiResponse.message || '모델 목록을 불러오는데 실패했습니다.');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '알 수 없는 오류가 발생했습니다.');
        console.error('Failed to fetch models:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchModels();
  }, []);

  const selectedModelInfo = models.find(m => m.value === selectedModel) || models[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleModelSelect = (model: ModelType) => {
    onModelChange(model);
    setIsOpen(false);
  };

  return (
    <div className="model-selector" ref={dropdownRef}>
      <button
        className="model-selector-btn"
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading || error !== null || models.length === 0}
      >
        <span className="model-selector-label">
          {isLoading ? '로딩 중...' : error ? '오류 발생' : selectedModelInfo?.label || '모델 선택'}
        </span>
        <span className={`model-selector-arrow ${isOpen ? 'open' : ''}`}>▼</span>
      </button>

      {isOpen && !isLoading && !error && models.length > 0 && (
        <div className="model-selector-dropdown">
          {models.map((model) => (
            <div
              key={model.value}
              className={`model-option ${selectedModel === model.value ? 'selected' : ''}`}
              onClick={() => handleModelSelect(model.value)}
            >
              <div className="model-option-label">{model.label}</div>
              <div className="model-option-description">{model.description}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ModelSelector;

import React, { useState, useRef, useEffect } from 'react';
import './ModelSelector.css';
import { ModelType } from '../../types/chat';

interface ModelSelectorProps {
  selectedModel: ModelType;
  onModelChange: (model: ModelType) => void;
}

const MODELS: { value: ModelType; label: string; description: string }[] = [
  { value: 'gpt-5-nano', label: 'GPT-5 Nano', description: '빠르고 효율적인 모델' },
  { value: 'gpt-4', label: 'GPT-4', description: '강력한 범용 모델' },
  { value: 'claude-3', label: 'Claude 3', description: '고급 추론 능력' },
  { value: 'gemini-pro', label: 'Gemini Pro', description: '멀티모달 지원' }
];

const ModelSelector: React.FC<ModelSelectorProps> = ({ selectedModel, onModelChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedModelInfo = MODELS.find(m => m.value === selectedModel) || MODELS[0];

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
      <button className="model-selector-btn" onClick={() => setIsOpen(!isOpen)}>
        <span className="model-selector-label">{selectedModelInfo.label}</span>
        <span className={`model-selector-arrow ${isOpen ? 'open' : ''}`}>▼</span>
      </button>

      {isOpen && (
        <div className="model-selector-dropdown">
          {MODELS.map((model) => (
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

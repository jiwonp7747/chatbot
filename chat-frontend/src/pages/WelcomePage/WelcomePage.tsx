import React from 'react';
import './WelcomePage.css';
import ModelSelector from '../../components/ModelSelector/ModelSelector';
import { ModelType } from '../../types/chat';

interface WelcomePageProps {
  selectedModel: ModelType;
  onModelChange: (model: ModelType) => void;
}

const WelcomePage: React.FC<WelcomePageProps> = ({ selectedModel, onModelChange }) => {
  return (
    <div className="welcome-screen">
      <div className="welcome-content">
        <h1 className="welcome-title">Bistelligence AI</h1>
        <p className="welcome-subtitle">무엇을 도와드릴까요?</p>
        <div className="model-selector-wrapper">
          <ModelSelector
            selectedModel={selectedModel}
            onModelChange={onModelChange}
          />
        </div>
      </div>
    </div>
  );
};

export default WelcomePage;

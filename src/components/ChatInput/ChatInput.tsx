import React, { useState, useRef, useEffect } from 'react';
import './ChatInput.css';

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  placeholder?: string;
  isStreaming?: boolean;
}

const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  onStop,
  disabled = false,
  placeholder = '메시지를 입력하세요...',
  isStreaming = false
}) => {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [message]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isStreaming) {
      // 스트리밍 중일 때는 중지
      onStop?.();
    } else if (message.trim() && !disabled) {
      // 일반 메시지 전송
      onSend(message.trim());
      setMessage('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <div className="chat-input-container">
        <textarea
          ref={textareaRef}
          className="chat-input-field"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
        />
        <button
          type="submit"
          className="chat-input-send"
          disabled={!isStreaming && (!message.trim() || disabled)}
        >
          {isStreaming ? (
            // 중지 아이콘 (정사각형)
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="currentColor"
              stroke="none"
            >
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            // 보내기 아이콘 (종이비행기)
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          )}
        </button>
      </div>
      <div className="chat-input-hint">
        <span>Enter로 전송, Shift+Enter로 줄바꿈</span>
      </div>
    </form>
  );
};

export default ChatInput;

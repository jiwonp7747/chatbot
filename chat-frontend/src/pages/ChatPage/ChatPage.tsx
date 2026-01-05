import React, {useEffect} from 'react';
import './ChatPage.css';
import ChatMessage from '../../components/ChatMessage/ChatMessage';
import ModelSelector from '../../components/ModelSelector/ModelSelector';
import { ChatSession, ModelType } from '../../types/chat';

interface ChatPageProps {
  session: ChatSession;
  streamingContent: string;
  isStreaming: boolean;
  onModelChange: (model: ModelType) => void;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
}

const ChatPage: React.FC<ChatPageProps> = ({
  session,
  streamingContent,
  isStreaming,
  onModelChange,
  messagesEndRef
}) => {
  useEffect(() => {
    console.log("chat page current session: {}", session)
  }, [session.id]);
  return (
    <>
      <div className="chat-header">
        <h2 className="chat-title">{session.title}</h2>
        <ModelSelector
          selectedModel={session.model}
          onModelChange={onModelChange}
        />
      </div>
      <div className="messages-container">
        {session.messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        {isStreaming && streamingContent && (
          <ChatMessage
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamingContent,
              timestamp: Date.now()
            }}
          />
        )}
        <div ref={messagesEndRef} />
      </div>
    </>
  );
};

export default ChatPage;

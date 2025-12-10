import React, { useState, useEffect, useRef } from 'react';
import './App.css';
import Sidebar from './components/Sidebar/Sidebar';
import ChatInput from './components/ChatInput/ChatInput';
import WelcomePage from './pages/WelcomePage/WelcomePage';
import ChatPage from './pages/ChatPage/ChatPage';
import { ChatSession, Message, ModelType, ChatResponse } from './types/chat';
import { chatService } from './services/chatService';
import { storage } from './utils/storage';

function App() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<ModelType>('gpt-5-nano');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const currentSession = sessions.find(s => s.id === currentSessionId);

  useEffect(() => {
    const loadSessions = async () => {
      try {
        const fetchedSessions = await chatService.fetchSessions();
        setSessions(fetchedSessions);
      } catch (error) {
        console.error('세션 목록 로드 실패:', error);
        // 오류 발생 시 로컬 스토리지에서 폴백
        const loadedSessions = storage.getSessions();
        setSessions(loadedSessions);
      }
    };

    loadSessions();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [currentSession?.messages, streamingContent]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const createNewSession = (firstMessage?: string): ChatSession => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: firstMessage?.slice(0, 30) || '새 채팅',
      messages: [],
      model: selectedModel,
      createdAt: Date.now(),
      updatedAt: Date.now()
    };
    return newSession;
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setStreamingContent('');
  };

  const handleSessionSelect = (sessionId: string) => {
    const loadedSessions = storage.getSessions();
    setSessions(loadedSessions);
    setCurrentSessionId(sessionId);
    setStreamingContent('');
  };

  const handleSendMessage = async (content: string) => {
    let targetSessionId = currentSessionId;

    if (!targetSessionId) {
      const newSession = createNewSession(content);
      setSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);
      targetSessionId = newSession.id;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now()
    };

    setSessions(prev => prev.map(s => {
      if (s.id === targetSessionId) {
        const updated = {
          ...s,
          messages: [...s.messages, userMessage],
          updatedAt: Date.now()
        };
        storage.saveSession(updated);
        return updated;
      }
      return s;
    }));

    setIsStreaming(true);
    setStreamingContent('');

    const modelToUse = sessions.find(s => s.id === targetSessionId)?.model || selectedModel;

    chatService.streamChat(
      { prompt: content, model: modelToUse }, // request
      (response: ChatResponse) => { // onMessage
        if (response.status === 'streaming') {
          setStreamingContent(prev => prev + response.content);
        } else if (response.status === 'done') {
          setStreamingContent(prev => {
            const fullContent = prev + response.content;
            const assistantMessage: Message = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: fullContent,
              timestamp: Date.now()
            };

            setSessions(prevSessions => prevSessions.map(s => {
              if (s.id === targetSessionId) {
                const updated = {
                  ...s,
                  messages: [...s.messages, assistantMessage],
                  updatedAt: Date.now()
                };
                storage.saveSession(updated);
                return updated;
              }
              return s;
            }));
            return '';
          });
          setIsStreaming(false);

        } else if (response.status === 'error') {
          const errorMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `오류: ${response.error || '알 수 없는 오류가 발생했습니다'}`,
            timestamp: Date.now()
          };

          setSessions(prev => prev.map(s => {
            if (s.id === targetSessionId) {
              const updated = {
                ...s,
                messages: [...s.messages, errorMessage],
                updatedAt: Date.now()
              };
              storage.saveSession(updated);
              return updated;
            }
            return s;
          }));
          setStreamingContent('');
          setIsStreaming(false);
        }
      },
      (error: Error) => {// on Error
        console.error('Chat error:', error);
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: `연결 오류: ${error.message}`,
          timestamp: Date.now()
        };

        setSessions(prev => prev.map(s => {
          if (s.id === targetSessionId) {
            const updated = {
              ...s,
              messages: [...s.messages, errorMessage],
              updatedAt: Date.now()
            };
            storage.saveSession(updated);
            return updated;
          }
          return s;
        }));
        setStreamingContent('');
      },
      () => { // onComplete
        setIsStreaming(false);
      }
    );
  };


  return (
    <div className="app">
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSessionSelect={handleSessionSelect}
        onNewChat={handleNewChat}
      />
      <div className="main-content">
        { !currentSession ? (
            <WelcomePage
                selectedModel={selectedModel}
                onModelChange={setSelectedModel}
            />
        ):(<ChatPage
                key={currentSession.id}
                session={currentSession}
                streamingContent={streamingContent}
                isStreaming={isStreaming}
                onModelChange={(model) => {
                  const updated = { ...currentSession, model };
                  storage.saveSession(updated);
                  setSessions(prev => prev.map(s => s.id === updated.id ? updated : s));
                }}
                messagesEndRef={messagesEndRef}
            />)}
        <ChatInput
          onSend={handleSendMessage}
          disabled={isStreaming}
          placeholder={isStreaming ? '응답을 기다리는 중...' : '메시지를 입력하세요...'}
        />
      </div>
    </div>
  );
}

export default App;

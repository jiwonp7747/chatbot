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
  const [streamingSessionId, setStreamingSessionId] = useState<string | null>(null);
  const [streamingContentMap, setStreamingContentMap] = useState<Map<string, string>>(new Map());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const currentSession = sessions.find(s => s.id === currentSessionId);
  const isCurrentSessionStreaming = streamingSessionId !== null && streamingSessionId === currentSessionId;
  const streamingContent = currentSessionId ? (streamingContentMap.get(currentSessionId) || '') : '';

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
  };

  const handleSessionSelect = async (sessionId: string) => {
    try {
      setCurrentSessionId(sessionId);

      // API에서 메시지 로드
      const messages = await chatService.fetchMessages(sessionId);
      console.log("📨 로드된 메시지:", messages)

      // 세션의 메시지 업데이트
      setSessions(prevSessions => prevSessions.map(session => {
        if (session.id === sessionId) {
          return {
            ...session,
            messages: messages
          };
        }
        return session;
      }));

      console.log("select action current session: {}", sessionId)

    } catch (error) {
      console.error('메시지 로드 실패:', error);
      // 오류 발생 시 로컬 스토리지에서 폴백
      const loadedSessions = storage.getSessions();
      setSessions(loadedSessions);
      setCurrentSessionId(sessionId);
    }
  };

  const handleStopStreaming = () => {
    if (!streamingSessionId) return;

    // SSE 연결 종료
    chatService.closeConnection();

    // 현재까지 받은 메시지를 저장
    const partialContent = streamingContentMap.get(streamingSessionId) || '';

    if (partialContent) {
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: partialContent,
        timestamp: Date.now()
      };

      setSessions(prevSessions => prevSessions.map(s => {
        if (s.id === streamingSessionId) {
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
    }

    // 스트리밍 상태 정리
    setStreamingContentMap(prev => {
      const newMap = new Map(prev);
      newMap.delete(streamingSessionId);
      return newMap;
    });
    setStreamingSessionId(null);
  };

  const handleSendMessage = async (content: string) => {
    let targetSessionId = currentSessionId;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now()
    };

    if (!targetSessionId) {
      // 새 세션 생성 + 사용자 메시지 추가를 한 번에 처리
      const newSession = createNewSession(content);
      newSession.messages = [userMessage];

      setSessions(prev => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);
      targetSessionId = newSession.id;
      storage.saveSession(newSession);
    } else {
      // 기존 세션에 메시지 추가
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
    }

    // 스트리밍 시작: 세션 ID 설정 및 초기화
    setStreamingSessionId(targetSessionId);
    setStreamingContentMap(prev => {
      const newMap = new Map(prev);
      newMap.set(targetSessionId!, '');
      return newMap;
    });

    // TODO model type api 에서 가져오기
    const modelToUse = sessions.find(s => s.id === targetSessionId)?.model || selectedModel;

    chatService.streamChat(
      {
        prompt: content,
        model: modelToUse,
        chat_session_id: targetSessionId ? parseInt(targetSessionId) : null
      },
      (response: ChatResponse) => { // onMessage
        if (response.status === 'streaming') {
          // 스트리밍 중: 세션별 콘텐츠 누적
          setStreamingContentMap(prev => {
            const newMap = new Map(prev);
            const currentContent = newMap.get(targetSessionId!) || '';
            newMap.set(targetSessionId!, currentContent + response.content);
            return newMap;
          });
        } else if (response.status === 'done') {
          // 완료: 최종 메시지 저장 및 스트리밍 상태 정리
          setStreamingContentMap(prev => {
            const newMap = new Map(prev);
            const currentContent = newMap.get(targetSessionId!) || '';
            const fullContent = currentContent + response.content;

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

            // 스트리밍 완료: 맵에서 제거
            newMap.delete(targetSessionId!);
            return newMap;
          });
          setStreamingSessionId(null);

        } else if (response.status === 'error') {
          // 에러: 에러 메시지 저장 및 스트리밍 상태 정리
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

          setStreamingContentMap(prev => {
            const newMap = new Map(prev);
            newMap.delete(targetSessionId!);
            return newMap;
          });
          setStreamingSessionId(null);
        }
      },
      (error: Error) => { // onError
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

        setStreamingContentMap(prev => {
          const newMap = new Map(prev);
          newMap.delete(targetSessionId!);
          return newMap;
        });
        setStreamingSessionId(null);
      },
      () => { // onComplete
        setStreamingSessionId(null);
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
                isStreaming={isCurrentSessionStreaming}
                onModelChange={(model) => {
                  const updated = { ...currentSession, model };
                  storage.saveSession(updated);
                  setSessions(prev => prev.map(s => s.id === updated.id ? updated : s));
                }}
                messagesEndRef={messagesEndRef}
            />)}
        <ChatInput
          onSend={handleSendMessage}
          onStop={handleStopStreaming}
          isStreaming={isCurrentSessionStreaming}
          disabled={false}
          placeholder={isCurrentSessionStreaming ? '응답을 기다리는 중...' : '메시지를 입력하세요...'}
        />
      </div>
    </div>
  );
}

export default App;

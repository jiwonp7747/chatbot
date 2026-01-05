export const API_CONFIG = {
  baseUrl: process.env.REACT_APP_BASE_URL || 'localhost',
  basePort: process.env.REACT_APP_BASE_PORT || '8000',
  endpoints: {
    // streamChat: '/chat/stream-chat',
    streamChat: '/chat/stream-chat-graph',
    sessions: '/chat/session',
    messages: '/chat/message',
    model: '/chat/model'
  }
};

export const getStreamChatUrl = (): string => {
  return `http://${API_CONFIG.baseUrl}:${API_CONFIG.basePort}${API_CONFIG.endpoints.streamChat}`;
};

export const getSessionsUrl = (): string => {
  return `http://${API_CONFIG.baseUrl}:${API_CONFIG.basePort}${API_CONFIG.endpoints.sessions}`;
};

export const getMessagesUrl = (sessionId: string): string => {
  return `http://${API_CONFIG.baseUrl}:${API_CONFIG.basePort}${API_CONFIG.endpoints.messages}/${sessionId}`;
};

export const getAvailAbleModelListUrl = (): string => {
  return `http://${API_CONFIG.baseUrl}:${API_CONFIG.basePort}${API_CONFIG.endpoints.model}`;
}
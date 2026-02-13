export const API_CONFIG = {
  baseUrl: import.meta.env.VITE_BASE_URL || 'localhost',
  endpoints: {
    streamChat: '/chat/stream-chat-graph',
    sessions: '/chat/session',
    messages: '/chat/message',
    model: '/chat/model'
  }
};

export const getStreamChatUrl = (): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.streamChat}`;
};

export const getSessionsUrl = (): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.sessions}`;
};

export const getMessagesUrl = (sessionId: string): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.messages}/${sessionId}`;
};

export const getDeleteSessionUrl = (sessionId: string): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.sessions}/${sessionId}`;
};

export const getUpdateSessionTitleUrl = (sessionId: string): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.sessions}/${sessionId}/title`;
};

export const getAvailAbleModelListUrl = (): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.model}`;
};

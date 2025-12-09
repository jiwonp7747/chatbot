export const API_CONFIG = {
  baseUrl: process.env.REACT_APP_BASE_URL || 'localhost',
  basePort: process.env.REACT_APP_BASE_PORT || '8000',
  endpoints: {
    streamChat: '/chat/stream-chat'
  }
};

export const getStreamChatUrl = (): string => {
  return `http://${API_CONFIG.baseUrl}:${API_CONFIG.basePort}${API_CONFIG.endpoints.streamChat}`;
};
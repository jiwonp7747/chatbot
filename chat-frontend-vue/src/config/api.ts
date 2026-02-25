const normalizeBaseUrl = (rawBaseUrl: string): string => {
  const withProtocol = /^https?:\/\//.test(rawBaseUrl) ? rawBaseUrl : `http://${rawBaseUrl}`;
  return withProtocol.replace(/\/+$/, '');
};

const resolveDefaultBaseUrl = (): string => {
  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `http://${window.location.hostname}:8000`;
  }
  return 'http://localhost:8000';
};

export const API_CONFIG = {
  baseUrl: normalizeBaseUrl(import.meta.env.VITE_BASE_URL || resolveDefaultBaseUrl()),
  endpoints: {
    streamChat: '/chat/stream-chat-graph',
    sessions: '/chat/session',
    messages: '/chat/message',
    model: '/chat/model',
    mcpTools: '/mcp/tools',
    ragTags: '/rag/tags/tree',
    resumeChat: '/chat/resume',
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

export const getMcpToolsUrl = (): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.mcpTools}`;
};

export const getRagTagsUrl = (): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.ragTags}`;
};

export const getResumeChatUrl = (): string => {
  return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.resumeChat}`;
};

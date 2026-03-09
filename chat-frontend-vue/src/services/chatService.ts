import {
  getStreamChatUrl,
  getSessionsUrl,
  getMessagesUrl,
  getDeleteSessionUrl,
  getUpdateSessionTitleUrl,
  getMcpToolsUrl,
  getRagTagsUrl,
  getResumeChatUrl,
  getToolSchemasUrl,
} from '../config/api';
import {
  ChatRequest,
  ChatResponse,
  ResumeRequest,
  SessionsApiResponse,
  ChatSession,
  MessagesApiResponse,
  Message,
  ApiResponse,
  SessionData,
  McpToolsApiResponse,
  McpTool,
  RagTagsApiResponse,
  TagTreeNode,
  ToolSchema,
} from '../types/chat';
import Cookies from "js-cookie";

export class ChatService {
  private abortController: AbortController | null = null;

  async streamChat(
    request: ChatRequest,
    onMessage: (response: ChatResponse) => void,
    onError: (error: Error) => void,
    onComplete: () => void
  ): Promise<void> {
    try {
      this.closeConnection();

      const url = getStreamChatUrl();
      const token = Cookies.get('LOGIN_TOKEN');
      this.abortController = new AbortController();

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          prompt: request.prompt,
          model: request.model,
          chat_session_id: request.chat_session_id ?? null,
          rag_tags: request.rag_tags ?? null
        }),
        signal: this.abortController.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          onComplete();
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6).trim();
              if (jsonStr) {
                const data: ChatResponse = JSON.parse(jsonStr);
                console.log('[ChatResponse]', data.status, data);

                onMessage(data);

                if (data.status === 'progress') {
                  continue;
                } else if (data.status === 'streaming') {
                  continue;
                } else if (data.status === 'done') {
                  this.closeConnection();
                  return;
                } else if (data.status === 'error') {
                  this.closeConnection();
                  onComplete();
                  return;
                } else if (data.status === 'confirm') {
                  // HITL: 확인 대기 — 스트림 정상 종료 (에러 아님)
                  onComplete();
                  return;
                }
              }
            } catch (error) {
              console.error('Error parsing SSE data:', error);
            }
          }
        }
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Request was aborted');
      } else {
        console.error('Error starting SSE connection:', error);
        onError(error as Error);
      }
      onComplete();
    }
  }

  closeConnection(): void {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  async resumeChat(
    request: ResumeRequest,
    onMessage: (response: ChatResponse) => void,
    onError: (error: Error) => void,
    onComplete: () => void
  ): Promise<void> {
    try {
      this.closeConnection();

      const url = getResumeChatUrl();
      const token = Cookies.get('LOGIN_TOKEN');
      this.abortController = new AbortController();

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(request),
        signal: this.abortController.signal
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          onComplete();
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const jsonStr = line.slice(6).trim();
              if (jsonStr) {
                const data: ChatResponse = JSON.parse(jsonStr);
                console.log('[ChatResponse:resume]', data.status, data);

                onMessage(data);

                if (data.status === 'done') {
                  this.closeConnection();
                  return;
                } else if (data.status === 'error') {
                  this.closeConnection();
                  onComplete();
                  return;
                } else if (data.status === 'confirm') {
                  // HITL 연쇄 확인 — 스트림 정상 종료
                  onComplete();
                  return;
                }
              }
            } catch (error) {
              console.error('Error parsing SSE data:', error);
            }
          }
        }
      }

    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log('Resume request was aborted');
      } else {
        console.error('Error in resume SSE connection:', error);
        onError(error as Error);
      }
      onComplete();
    }
  }

  async fetchSessions(): Promise<ChatSession[]> {
    try {
      const url = getSessionsUrl();
      const token = Cookies.get('LOGIN_TOKEN');
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const apiResponse: SessionsApiResponse = await response.json();

      if (!apiResponse.success) {
        throw new Error(apiResponse.message || '세션 목록을 불러오는데 실패했습니다.');
      }

      return apiResponse.data.map(session => ({
        id: session.chat_session_id.toString(),
        title: session.session_title,
        messages: [],
        model: 'gpt-5-nano' as const,
        createdAt: new Date(session.created_at).getTime(),
        updatedAt: new Date(session.updated_at).getTime(),
      }));

    } catch (error) {
      console.error('Error fetching sessions:', error);
      throw error;
    }
  }

  async fetchMessages(sessionId: string): Promise<Message[]> {
    try {
      const url = getMessagesUrl(sessionId);
      const token = Cookies.get('LOGIN_TOKEN');
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const apiResponse: MessagesApiResponse = await response.json();

      if (!apiResponse.success) {
        throw new Error(apiResponse.message || '메시지를 불러오는데 실패했습니다.');
      }

      return apiResponse.data.map(msg => ({
        id: msg.chat_message_id.toString(),
        role: msg.role === 'system' ? 'assistant' : msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at).getTime(),
      }));

    } catch (error) {
      console.error('Error fetching messages:', error);
      throw error;
    }
  }

  async deleteSession(sessionId: string): Promise<void> {
    const url = getDeleteSessionUrl(sessionId);
    const token = Cookies.get('LOGIN_TOKEN');
    const response = await fetch(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const apiResponse: ApiResponse<null> = await response.json();
    if (!apiResponse.success) {
      throw new Error(apiResponse.message || '세션 삭제에 실패했습니다.');
    }
  }

  async updateSessionTitle(sessionId: string, sessionTitle: string): Promise<ChatSession> {
    const url = getUpdateSessionTitleUrl(sessionId);
    const token = Cookies.get('LOGIN_TOKEN');
    const response = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ session_title: sessionTitle }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const apiResponse: ApiResponse<SessionData> = await response.json();
    if (!apiResponse.success) {
      throw new Error(apiResponse.message || '세션 제목 변경에 실패했습니다.');
    }

    const updated = apiResponse.data;
    return {
      id: updated.chat_session_id.toString(),
      title: updated.session_title,
      messages: [],
      model: 'gpt-5-nano' as const,
      createdAt: new Date(updated.created_at).getTime(),
      updatedAt: new Date(updated.updated_at).getTime(),
    };
  }

  async fetchMcpTools(): Promise<McpTool[]> {
    const url = getMcpToolsUrl();
    const token = Cookies.get('LOGIN_TOKEN');
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const apiResponse: McpToolsApiResponse = await response.json();
    if (!apiResponse.success) {
      throw new Error(apiResponse.message || 'MCP 도구 목록을 불러오는데 실패했습니다.');
    }

    return apiResponse.data;
  }

  async fetchRagTags(): Promise<TagTreeNode[]> {
    const url = getRagTagsUrl();
    const token = Cookies.get('LOGIN_TOKEN');
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const apiResponse: RagTagsApiResponse = await response.json();
    if (!apiResponse.success) {
      throw new Error(apiResponse.message || 'RAG 태그 목록을 불러오는데 실패했습니다.');
    }

    return apiResponse.data;
  }

  async fetchToolSchemas(toolNames?: string[]): Promise<ToolSchema[]> {
    const url = getToolSchemasUrl();
    const token = Cookies.get('LOGIN_TOKEN');
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ tool_names: toolNames ?? null }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const apiResponse: ApiResponse<ToolSchema[]> = await response.json();
    if (!apiResponse.success) {
      throw new Error(apiResponse.message || '도구 스키마를 불러오는데 실패했습니다.');
    }

    return apiResponse.data;
  }
}

export const chatService = new ChatService();

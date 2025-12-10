import { getStreamChatUrl, getSessionsUrl } from '../config/api';
import { ChatRequest, ChatResponse, SessionsApiResponse, ChatSession } from '../types/chat';

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
      this.abortController = new AbortController();

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          prompt: request.prompt,
          model: request.model
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
                onMessage(data);

                if (data.status === 'done') {
                  this.closeConnection();
                  return;
                } else if (data.status === 'error') {
                  this.closeConnection();
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

  async fetchSessions(): Promise<ChatSession[]> {
    try {
      const url = getSessionsUrl();
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const apiResponse: SessionsApiResponse = await response.json();

      if (!apiResponse.success) {
        throw new Error(apiResponse.message || '세션 목록을 불러오는데 실패했습니다.');
      }

      // API 응답을 ChatSession 형식으로 변환
      return apiResponse.data.map(session => ({
        id: session.chat_session_id.toString(),
        title: session.session_title,
        messages: [],
        model: 'gpt-5-nano' as const, // 기본 모델
        createdAt: new Date(session.created_at).getTime(),
        updatedAt: new Date(session.updated_at).getTime(),
      }));

    } catch (error) {
      console.error('Error fetching sessions:', error);
      throw error;
    }
  }
}

export const chatService = new ChatService();

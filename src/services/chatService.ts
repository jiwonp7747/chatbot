import { getStreamChatUrl } from '../config/api';
import { ChatRequest, ChatResponse } from '../types/chat';

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
}

export const chatService = new ChatService();

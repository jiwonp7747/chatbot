import { defineStore } from 'pinia';
import { ChatSession, Message, ModelType, ChatResponse } from '../types/chat';
import { chatService } from '../services/chatService';
import { storage } from '../utils/storage';

interface PendingConfirm {
  threadId: string;
  toolName: string;
  toolArgs: Record<string, unknown>;
}

interface SubProgressEntry {
  content: string;
  tools: string[];
  parallel: boolean;
  agent: string;
}

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  selectedModel: ModelType;
  streamingSessionId: string | null;
  streamingContentMap: Record<string, string>;
  streamingStatusMap: Record<string, 'progress' | 'streaming' | 'confirm'>;
  selectedRagTags: string[];
  pendingConfirm: PendingConfirm | null;
  subProgressMap: Record<number, SubProgressEntry[]>;
}

export const useChatStore = defineStore('chat', {
  state: (): ChatState => ({
    sessions: [],
    currentSessionId: null,
    selectedModel: 'gpt-5-nano',
    streamingSessionId: null,
    streamingContentMap: {},
    streamingStatusMap: {},
    selectedRagTags: [],
    pendingConfirm: null,
    subProgressMap: {},
  }),

  getters: {
    currentSession(state): ChatSession | undefined {
      return state.sessions.find(s => s.id === state.currentSessionId);
    },
    isStreaming(state): boolean {
      return state.streamingSessionId !== null && state.streamingSessionId === state.currentSessionId;
    },
    currentStreamingContent(state): string {
      return state.currentSessionId ? (state.streamingContentMap[state.currentSessionId] || '') : '';
    },
  },

  actions: {
    async loadSessions() {
      try {
        const fetchedSessions = await chatService.fetchSessions();
        this.sessions = fetchedSessions;
      } catch (error) {
        console.error('세션 목록 로드 실패:', error);
        this.sessions = storage.getSessions();
      }
    },

    newChat() {
      this.currentSessionId = null;
    },

    async selectSession(sessionId: string) {
      try {
        this.currentSessionId = sessionId;

        const messages = await chatService.fetchMessages(sessionId);

        const idx = this.sessions.findIndex(s => s.id === sessionId);
        if (idx !== -1) {
          this.sessions[idx] = { ...this.sessions[idx], messages };
        }
      } catch (error) {
        console.error('메시지 로드 실패:', error);
        this.sessions = storage.getSessions();
        this.currentSessionId = sessionId;
      }
    },

    stopStreaming() {
      if (!this.streamingSessionId) return;

      chatService.closeConnection();

      const partialContent = this.streamingContentMap[this.streamingSessionId] || '';

      if (partialContent) {
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: partialContent,
          timestamp: Date.now()
        };

        const idx = this.sessions.findIndex(s => s.id === this.streamingSessionId);
        if (idx !== -1) {
          const updated = {
            ...this.sessions[idx],
            messages: [...this.sessions[idx].messages, assistantMessage],
            updatedAt: Date.now()
          };
          this.sessions[idx] = updated;
          storage.saveSession(updated);
        }
      }

      delete this.streamingContentMap[this.streamingSessionId];
      delete this.streamingStatusMap[this.streamingSessionId];
      this.streamingSessionId = null;
    },

    async sendMessage(content: string) {
      let targetSessionId = this.currentSessionId;

      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content,
        timestamp: Date.now()
      };

      if (!targetSessionId) {
        const newSession: ChatSession = {
          id: Date.now().toString(),
          title: content.slice(0, 30) || '새 채팅',
          messages: [userMessage],
          model: this.selectedModel,
          createdAt: Date.now(),
          updatedAt: Date.now()
        };

        this.sessions.unshift(newSession);
        this.currentSessionId = newSession.id;
        targetSessionId = newSession.id;
        storage.saveSession(newSession);
      } else {
        const idx = this.sessions.findIndex(s => s.id === targetSessionId);
        if (idx !== -1) {
          const updated = {
            ...this.sessions[idx],
            messages: [...this.sessions[idx].messages, userMessage],
            updatedAt: Date.now()
          };
          this.sessions[idx] = updated;
          storage.saveSession(updated);
        }
      }

      this.streamingSessionId = targetSessionId;
      this.streamingContentMap[targetSessionId!] = '';

      const modelToUse = this.sessions.find(s => s.id === targetSessionId)?.model || this.selectedModel;

      // Keep a local reference for closures
      const sessionId = targetSessionId!;

      chatService.streamChat(
        {
          prompt: content,
          model: modelToUse,
          chat_session_id: sessionId ? parseInt(sessionId) : null,
          rag_tags: this.selectedRagTags
        },
        (response: ChatResponse) => {
          if (response.status === 'progress') {
            this.streamingStatusMap[sessionId] = 'progress';
            this.streamingContentMap[sessionId] = response.content;
          } else if (response.status === 'sub_progress') {
            const numericId = parseInt(sessionId);
            if (!this.subProgressMap[numericId]) {
              this.subProgressMap[numericId] = [];
            }
            this.subProgressMap[numericId].push({
              content: response.content,
              tools: response.sub_tools || [],
              parallel: response.parallel || false,
              agent: response.agent_name || '',
            });
          } else if (response.status === 'streaming') {
            const previousStatus = this.streamingStatusMap[sessionId];
            const isTransitionFromProgress = previousStatus === 'progress';

            this.streamingStatusMap[sessionId] = 'streaming';

            // Clear sub_progress on first streaming chunk
            const numericId = parseInt(sessionId);
            if (isTransitionFromProgress && this.subProgressMap[numericId]) {
              delete this.subProgressMap[numericId];
            }

            if (isTransitionFromProgress) {
              this.streamingContentMap[sessionId] = response.content;
            } else {
              this.streamingContentMap[sessionId] = (this.streamingContentMap[sessionId] || '') + response.content;
            }
          } else if (response.status === 'done') {
            const currentContent = this.streamingContentMap[sessionId] || '';
            const fullContent = currentContent + response.content;

            const assistantMessage: Message = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: fullContent,
              timestamp: Date.now()
            };

            const idx = this.sessions.findIndex(s => s.id === sessionId);
            if (idx !== -1) {
              const updated = {
                ...this.sessions[idx],
                messages: [...this.sessions[idx].messages, assistantMessage],
                updatedAt: Date.now()
              };
              this.sessions[idx] = updated;
              storage.saveSession(updated);
            }

            delete this.streamingContentMap[sessionId];
            delete this.streamingStatusMap[sessionId];
            delete this.subProgressMap[parseInt(sessionId)];
            this.streamingSessionId = null;
          } else if (response.status === 'confirm') {
            this.streamingStatusMap[sessionId] = 'confirm';
            this.streamingContentMap[sessionId] = response.content;
            this.pendingConfirm = {
              threadId: response.thread_id!,
              toolName: response.tool_name!,
              toolArgs: response.tool_args || {},
            };
          } else if (response.status === 'error') {
            const errorMessage: Message = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: `오류: ${response.error || '알 수 없는 오류가 발생했습니다'}`,
              timestamp: Date.now()
            };

            const idx = this.sessions.findIndex(s => s.id === sessionId);
            if (idx !== -1) {
              const updated = {
                ...this.sessions[idx],
                messages: [...this.sessions[idx].messages, errorMessage],
                updatedAt: Date.now()
              };
              this.sessions[idx] = updated;
              storage.saveSession(updated);
            }

            delete this.streamingContentMap[sessionId];
            delete this.streamingStatusMap[sessionId];
            delete this.subProgressMap[parseInt(sessionId)];
            this.streamingSessionId = null;
          }
        },
        (error: Error) => {
          console.error('Chat error:', error);
          const errorMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `연결 오류: ${error.message}`,
            timestamp: Date.now()
          };

          const idx = this.sessions.findIndex(s => s.id === sessionId);
          if (idx !== -1) {
            const updated = {
              ...this.sessions[idx],
              messages: [...this.sessions[idx].messages, errorMessage],
              updatedAt: Date.now()
            };
            this.sessions[idx] = updated;
            storage.saveSession(updated);
          }

          delete this.streamingContentMap[sessionId];
          delete this.streamingStatusMap[sessionId];
          delete this.subProgressMap[parseInt(sessionId)];
          this.streamingSessionId = null;
        },
        () => {
          // HITL confirm 대기 중이면 streamingSessionId 유지
          if (!this.pendingConfirm) {
            this.streamingSessionId = null;
          }
        }
      );
    },

    updateSessionModel(model: ModelType) {
      if (!this.currentSessionId) return;
      const idx = this.sessions.findIndex(s => s.id === this.currentSessionId);
      if (idx !== -1) {
        const updated = { ...this.sessions[idx], model };
        this.sessions[idx] = updated;
        storage.saveSession(updated);
      }
    },

    async deleteSession(sessionId: string) {
      await chatService.deleteSession(sessionId);

      this.sessions = this.sessions.filter(session => session.id !== sessionId);
      storage.deleteSession(sessionId);

      if (this.currentSessionId === sessionId) {
        this.currentSessionId = null;
      }
    },

    async renameSession(sessionId: string, newTitle: string) {
      const trimmedTitle = newTitle.trim();
      if (!trimmedTitle) return;

      const updatedFromApi = await chatService.updateSessionTitle(sessionId, trimmedTitle);
      const idx = this.sessions.findIndex(session => session.id === sessionId);
      if (idx === -1) return;

      const updatedSession = {
        ...this.sessions[idx],
        title: updatedFromApi.title,
        updatedAt: updatedFromApi.updatedAt,
      };
      this.sessions[idx] = updatedSession;
      storage.saveSession(updatedSession);
    },

    _handleResumeResponse(sessionId: string, response: ChatResponse) {
      if (response.status === 'progress') {
        this.streamingStatusMap[sessionId] = 'progress';
        this.streamingContentMap[sessionId] = response.content;
      } else if (response.status === 'sub_progress') {
        const numericId = parseInt(sessionId);
        if (!this.subProgressMap[numericId]) {
          this.subProgressMap[numericId] = [];
        }
        this.subProgressMap[numericId].push({
          content: response.content,
          tools: response.sub_tools || [],
          parallel: response.parallel || false,
          agent: response.agent_name || '',
        });
      } else if (response.status === 'streaming') {
        const previousStatus = this.streamingStatusMap[sessionId];
        const isTransitionFromProgress = previousStatus === 'progress';

        this.streamingStatusMap[sessionId] = 'streaming';

        // Clear sub_progress on first streaming chunk
        const numericId = parseInt(sessionId);
        if (isTransitionFromProgress && this.subProgressMap[numericId]) {
          delete this.subProgressMap[numericId];
        }

        if (isTransitionFromProgress) {
          this.streamingContentMap[sessionId] = response.content;
        } else {
          this.streamingContentMap[sessionId] = (this.streamingContentMap[sessionId] || '') + response.content;
        }
      } else if (response.status === 'confirm') {
        this.streamingStatusMap[sessionId] = 'confirm';
        this.streamingContentMap[sessionId] = response.content;
        this.pendingConfirm = {
          threadId: response.thread_id!,
          toolName: response.tool_name!,
          toolArgs: response.tool_args || {},
        };
      } else if (response.status === 'done') {
        const currentContent = this.streamingContentMap[sessionId] || '';
        const fullContent = currentContent + response.content;

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: fullContent,
          timestamp: Date.now()
        };

        const idx = this.sessions.findIndex(s => s.id === sessionId);
        if (idx !== -1) {
          const updated = {
            ...this.sessions[idx],
            messages: [...this.sessions[idx].messages, assistantMessage],
            updatedAt: Date.now()
          };
          this.sessions[idx] = updated;
          storage.saveSession(updated);
        }

        delete this.streamingContentMap[sessionId];
        delete this.streamingStatusMap[sessionId];
        delete this.subProgressMap[parseInt(sessionId)];
        this.streamingSessionId = null;
      } else if (response.status === 'error') {
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: `오류: ${response.error || '알 수 없는 오류가 발생했습니다'}`,
          timestamp: Date.now()
        };

        const idx = this.sessions.findIndex(s => s.id === sessionId);
        if (idx !== -1) {
          const updated = {
            ...this.sessions[idx],
            messages: [...this.sessions[idx].messages, errorMessage],
            updatedAt: Date.now()
          };
          this.sessions[idx] = updated;
          storage.saveSession(updated);
        }

        delete this.streamingContentMap[sessionId];
        delete this.streamingStatusMap[sessionId];
        delete this.subProgressMap[parseInt(sessionId)];
        this.streamingSessionId = null;
      }
    },

    approveToolCall() {
      if (!this.pendingConfirm || !this.streamingSessionId) return;
      const { threadId } = this.pendingConfirm;
      const sessionId = this.streamingSessionId;
      this.pendingConfirm = null;
      this.streamingContentMap[sessionId] = '';
      this.streamingStatusMap[sessionId] = 'progress';

      const modelToUse = this.sessions.find(s => s.id === sessionId)?.model || this.selectedModel;

      chatService.resumeChat(
        {
          thread_id: threadId,
          approved: true,
          model: modelToUse,
          chat_session_id: parseInt(sessionId) || null,
        },
        (response: ChatResponse) => this._handleResumeResponse(sessionId, response),
        (error: Error) => {
          console.error('Resume error:', error);
          delete this.streamingContentMap[sessionId];
          delete this.streamingStatusMap[sessionId];
          this.streamingSessionId = null;
        },
        () => {}
      );
    },

    rejectToolCall() {
      if (!this.pendingConfirm || !this.streamingSessionId) return;
      const { threadId } = this.pendingConfirm;
      const sessionId = this.streamingSessionId;
      this.pendingConfirm = null;
      this.streamingContentMap[sessionId] = '';
      this.streamingStatusMap[sessionId] = 'progress';

      const modelToUse = this.sessions.find(s => s.id === sessionId)?.model || this.selectedModel;

      chatService.resumeChat(
        {
          thread_id: threadId,
          approved: false,
          model: modelToUse,
          chat_session_id: parseInt(sessionId) || null,
        },
        (response: ChatResponse) => this._handleResumeResponse(sessionId, response),
        (error: Error) => {
          console.error('Resume error:', error);
          delete this.streamingContentMap[sessionId];
          delete this.streamingStatusMap[sessionId];
          this.streamingSessionId = null;
        },
        () => {}
      );
    },
  },
});

import { defineStore } from 'pinia';
import { ChatSession, Message, ModelType, ChatResponse, HitlToolCall, ToolSchema, EditedToolCall, AvailableTool, ToolArtifact } from '../types/chat';
import { chatService } from '../services/chatService';
import { storage } from '../utils/storage';

interface PendingConfirm {
  threadId: string;
  toolCalls: HitlToolCall[];     // interrupt된 도구 목록
  // 동적 컨텍스트
  toolContext: string;           // 에이전트 판단 근거 (1회, 공통)
  availableTools: AvailableTool[];      // 수정 가능 도구 목록
  // 수정 모드 (EDIT decision)
  isEditing: boolean;
  toolSchemas: Record<string, ToolSchema>;     // 도구별 스키마
  editedArgs: Record<number, Record<string, unknown>>;  // idx → 수정된 인자
  editedToolNames: Record<number, string>;     // idx → 변경된 도구명
  schemasLoading: boolean;
  // 메시지 수정 모드 (거부 사유 반영하여 재시도)
  isMessageEditing: boolean;
  editMessage: string;
  // 거부 모드 (순수 거절)
  isRejecting: boolean;
}

interface SubProgressEntry {
  content: string;
  tools: string[];
  parallel: boolean;
  agent: string;
  artifact?: ToolArtifact;
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
  subProgressMap: Record<string, SubProgressEntry[]>;
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
      this.pendingConfirm = null;
    },

    async selectSession(sessionId: string) {
      this.pendingConfirm = null;
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
          id: crypto.randomUUID(),
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
          thread_id: sessionId || null,
          rag_tags: this.selectedRagTags
        },
        (response: ChatResponse) => {
          if (response.status === 'progress') {
            this.streamingStatusMap[sessionId] = 'progress';
            this.streamingContentMap[sessionId] = response.content;
          } else if (response.status === 'sub_progress') {
            if (!this.subProgressMap[sessionId]) {
              this.subProgressMap[sessionId] = [];
            }
            this.subProgressMap[sessionId].push({
              content: response.content,
              tools: response.sub_tools || [],
              parallel: response.parallel || false,
              agent: response.agent_name || '',
              artifact: response.artifact,
            });
          } else if (response.status === 'streaming') {
            const previousStatus = this.streamingStatusMap[sessionId];
            const isTransitionFromProgress = previousStatus === 'progress';

            this.streamingStatusMap[sessionId] = 'streaming';

            // Clear sub_progress on first streaming chunk
            if (isTransitionFromProgress && this.subProgressMap[sessionId]) {
              delete this.subProgressMap[sessionId];
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
            delete this.subProgressMap[sessionId];
            this.streamingSessionId = null;
          } else if (response.status === 'confirm') {
            this.streamingStatusMap[sessionId] = 'confirm';
            this.streamingContentMap[sessionId] = response.content;
            const toolCalls = response.tool_calls || [];
            this.pendingConfirm = {
              threadId: response.thread_id!,
              toolCalls,
              toolContext: response.tool_context || '',
              availableTools: response.available_tools || [],
              isEditing: false,
              toolSchemas: {},
              editedArgs: {},
              editedToolNames: {},
              schemasLoading: false,
              isMessageEditing: false,
              editMessage: '',
              isRejecting: false,
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
            delete this.subProgressMap[sessionId];
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
          delete this.subProgressMap[sessionId];
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
        if (!this.subProgressMap[sessionId]) {
          this.subProgressMap[sessionId] = [];
        }
        this.subProgressMap[sessionId].push({
          content: response.content,
          tools: response.sub_tools || [],
          parallel: response.parallel || false,
          agent: response.agent_name || '',
          artifact: response.artifact,
        });
      } else if (response.status === 'streaming') {
        const previousStatus = this.streamingStatusMap[sessionId];
        const isTransitionFromProgress = previousStatus === 'progress';

        this.streamingStatusMap[sessionId] = 'streaming';

        // Clear sub_progress on first streaming chunk
        if (isTransitionFromProgress && this.subProgressMap[sessionId]) {
          delete this.subProgressMap[sessionId];
        }

        if (isTransitionFromProgress) {
          this.streamingContentMap[sessionId] = response.content;
        } else {
          this.streamingContentMap[sessionId] = (this.streamingContentMap[sessionId] || '') + response.content;
        }
      } else if (response.status === 'confirm') {
        this.streamingStatusMap[sessionId] = 'confirm';
        this.streamingContentMap[sessionId] = response.content;
        const toolCalls = response.tool_calls || [];
        this.pendingConfirm = {
          threadId: response.thread_id!,
          toolCalls,
          toolContext: response.tool_context || '',
          availableTools: response.available_tools || [],
          isEditing: false,
          toolSchemas: {},
          editedArgs: {},
          editedToolNames: {},
          schemasLoading: false,
          isMessageEditing: false,
          editMessage: '',
          isRejecting: false,
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
        delete this.subProgressMap[sessionId];
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
        delete this.subProgressMap[sessionId];
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

    async toggleEditMode() {
      if (!this.pendingConfirm) return;
      const pc = this.pendingConfirm;
      pc.isEditing = !pc.isEditing;
      pc.isRejecting = false;
      pc.isMessageEditing = false;
      if (pc.isEditing) {
        // 현재 args로 pre-fill
        pc.editedArgs = {};
        pc.editedToolNames = {};
        pc.toolCalls.forEach((tc, idx) => {
          pc.editedArgs[idx] = { ...tc.args };
          pc.editedToolNames[idx] = tc.name;
        });
        // 스키마 fetch
        if (Object.keys(pc.toolSchemas).length === 0) {
          pc.schemasLoading = true;
          try {
            const allToolNames = [...new Set<string>([
              ...pc.toolCalls.map(tc => tc.name),
              ...pc.availableTools.map(t => t.name),
            ])];
            const schemas = await chatService.fetchToolSchemas(allToolNames);
            const schemaMap: Record<string, ToolSchema> = {};
            for (const s of schemas) {
              schemaMap[s.name] = s;
            }
            pc.toolSchemas = schemaMap;
          } catch (e) {
            console.error('스키마 로드 실패:', e);
          } finally {
            pc.schemasLoading = false;
          }
        }
      }
    },

    onToolNameChange(idx: number, newName: string) {
      if (!this.pendingConfirm) return;
      const pc = this.pendingConfirm;
      pc.editedToolNames[idx] = newName;
      // 새 도구의 default 값으로 args 리셋
      const schema = pc.toolSchemas[newName];
      if (schema?.schema?.properties) {
        const defaults: Record<string, unknown> = {};
        for (const [key, prop] of Object.entries(schema.schema.properties)) {
          defaults[key] = prop.default ?? null;
        }
        pc.editedArgs[idx] = defaults;
      } else {
        pc.editedArgs[idx] = {};
      }
    },

    submitEditedToolCall() {
      if (!this.pendingConfirm || !this.streamingSessionId) return;

      const pc = this.pendingConfirm;
      const sessionId = this.streamingSessionId;

      // edited_tool_calls 배열 구성
      const editedToolCalls: EditedToolCall[] = pc.toolCalls.map((_, idx) => ({
        name: pc.editedToolNames[idx] || pc.toolCalls[idx].name,
        args: pc.editedArgs[idx] || pc.toolCalls[idx].args,
      }));

      const threadId = pc.threadId;
      this.pendingConfirm = null;
      this.streamingContentMap[sessionId] = '';
      this.streamingStatusMap[sessionId] = 'progress';

      const modelToUse = this.sessions.find(s => s.id === sessionId)?.model || this.selectedModel;

      chatService.resumeChat(
        {
          thread_id: threadId,
          approved: true,
          model: modelToUse,
          edited_tool_calls: editedToolCalls,
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

    toggleMessageEditMode() {
      if (!this.pendingConfirm) return;
      const pc = this.pendingConfirm;
      pc.isMessageEditing = !pc.isMessageEditing;
      pc.isEditing = false;
      pc.isRejecting = false;
      if (pc.isMessageEditing) {
        pc.editMessage = '';
      }
    },

    submitMessageEdit() {
      if (!this.pendingConfirm || !this.streamingSessionId) return;

      const pc = this.pendingConfirm;
      const sessionId = this.streamingSessionId;
      const threadId = pc.threadId;
      const editMessage = pc.editMessage.trim();
      if (!editMessage) return;

      this.pendingConfirm = null;
      this.streamingContentMap[sessionId] = '';
      this.streamingStatusMap[sessionId] = 'progress';

      const modelToUse = this.sessions.find(s => s.id === sessionId)?.model || this.selectedModel;

      chatService.resumeChat(
        {
          thread_id: threadId,
          approved: false,
          model: modelToUse,
          edit_message: editMessage,
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

    toggleRejectMode() {
      if (!this.pendingConfirm) return;
      const pc = this.pendingConfirm;
      pc.isRejecting = !pc.isRejecting;
      pc.isEditing = false;
      pc.isMessageEditing = false;
    },

    submitReject() {
      if (!this.pendingConfirm || !this.streamingSessionId) return;

      const pc = this.pendingConfirm;
      const sessionId = this.streamingSessionId;
      const threadId = pc.threadId;

      this.pendingConfirm = null;
      this.streamingContentMap[sessionId] = '';
      this.streamingStatusMap[sessionId] = 'progress';

      const modelToUse = this.sessions.find(s => s.id === sessionId)?.model || this.selectedModel;

      chatService.resumeChat(
        {
          thread_id: threadId,
          approved: false,
          model: modelToUse,
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

import { ChatSession } from '../types/chat';

const STORAGE_KEY = 'bistelligence_chat_sessions';

export const storage = {
  getSessions(): ChatSession[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (error) {
      console.error('Error loading sessions:', error);
      return [];
    }
  },

  saveSessions(sessions: ChatSession[]): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch (error) {
      console.error('Error saving sessions:', error);
    }
  },

  getSession(sessionId: string): ChatSession | null {
    const sessions = this.getSessions();
    return sessions.find(s => s.id === sessionId) || null;
  },

  saveSession(session: ChatSession): void {
    const sessions = this.getSessions();
    const index = sessions.findIndex(s => s.id === session.id);

    if (index >= 0) {
      if (session.updatedAt < sessions[index].updatedAt) {
        console.warn('Ignored stale update for session:', session.id);
        return;
      }
      sessions[index] = session;
    } else {
      sessions.unshift(session);
    }

    this.saveSessions(sessions);
  },

  deleteSession(sessionId: string): void {
    const sessions = this.getSessions();
    const filtered = sessions.filter(s => s.id !== sessionId);
    this.saveSessions(filtered);
  }
};

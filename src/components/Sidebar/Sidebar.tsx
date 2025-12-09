import React from 'react';
import './Sidebar.css';
import { ChatSession } from '../../types/chat';

interface SidebarProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onNewChat: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  currentSessionId,
  onSessionSelect,
  onNewChat
}) => {
  const formatTimestamp = (timestamp: number): string => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return '오늘';
    if (diffDays === 1) return '어제';
    if (diffDays < 7) return `${diffDays}일 전`;
    return date.toLocaleDateString('ko-KR');
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">Bistelligence AI</h1>
        <button className="new-chat-btn" onClick={onNewChat}>
          <span className="new-chat-icon">+</span>
          새 채팅
        </button>
      </div>

      <div className="chat-list">
        {sessions.length === 0 ? (
          <div className="empty-state">
            <p>채팅 내역이 없습니다</p>
          </div>
        ) : (
          sessions.map((session) => (
            <div
              key={session.id}
              className={`chat-item ${currentSessionId === session.id ? 'active' : ''}`}
              onClick={() => onSessionSelect(session.id)}
            >
              <div className="chat-item-title">{session.title}</div>
              <div className="chat-item-info">
                <span className="chat-item-model">{session.model}</span>
                <span className="chat-item-date">{formatTimestamp(session.updatedAt)}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Sidebar;

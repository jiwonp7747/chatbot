from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.database import Base

class ChatSession(Base):
    __tablename__ = "chat_session"

    # BigInteger 사용, DB에서 Identity로 자동 생성되므로 server_default 등은 생략 가능
    chat_session_id = Column(BigInteger, primary_key=True, index=True)
    session_title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계 설정 (선택사항, 데이터 가져올 때 편함)
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete")


class ChatMessage(Base):
    __tablename__ = "chat_message"

    chat_message_id = Column(BigInteger, primary_key=True, index=True)
    role = Column(String)  # user / assistant / system
    content = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Foreign Key
    chat_session_id = Column(BigInteger, ForeignKey("chat_session.chat_session_id"))

    # 관계 설정
    session = relationship("ChatSession", back_populates="messages")

class ModelType(Base):
    __tablename__ = "model_type"

    model_id = Column(BigInteger, primary_key=True, index=True)
    model_name = Column(String, nullable=True)
    model_type = Column(String, nullable=True)
    summary = Column(String, nullable=True)

from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger
from sqlalchemy.sql import func

from db.database import Base

class ChatSession(Base):
    __tablename__ = "chat_session"

    thread_id = Column(String, primary_key=True, index=True)
    session_title = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ModelType(Base):
    __tablename__ = "model_type"

    model_id = Column(BigInteger, primary_key=True, index=True)
    model_name = Column(String, nullable=True)
    model_type = Column(String, nullable=True)  # 외부 입력/선택용 model key
    provider = Column(String, nullable=True)
    api_model = Column(String, nullable=True)  # 실제 provider SDK 호출 모델명
    is_active = Column(Boolean, nullable=True, default=True)
    summary = Column(String, nullable=True)

class PromptTemplate(Base):
    __tablename__ = "prompt_template"

    prompt_id = Column(BigInteger, primary_key=True, index=True)
    prompt_name = Column(String, nullable=True)
    prompt_type = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=True)
    priority = Column(Integer, nullable=True)
    content = Column(String, nullable=True)


class LargeData(Base):
    __tablename__ = "large_data"

    id = Column(BigInteger, primary_key=True, index=True)
    path = Column(String, nullable=False, unique=True, index=True)
    content = Column(String, nullable=False)  # TEXT type for large content
    thread_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

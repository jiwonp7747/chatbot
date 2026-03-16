from sqlalchemy import Column, Integer, String, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB

from db.database import Base

class CheckPointMigration(Base):
    __tablename__ = "checkpoint_migrations"

    v = Column(Integer, primary_key=True)

class CheckPoint(Base):
    __tablename__ = "checkpoints"

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default='')
    checkpoint_id = Column(String, primary_key=True)

    parent_checkpoint_id = Column(String, nullable=True)
    type = Column(String, nullable=True)
    checkpoint = Column(JSONB, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, default={})

class CheckpointBlob(Base):
    __tablename__ = "checkpoint_blobs"

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default='')
    channel = Column(String, primary_key=True)
    version = Column(String, primary_key=True)

    type = Column(String, nullable=False)
    blob = Column(LargeBinary, nullable=True)

class CheckpointWrite(Base):
    __tablename__ = "checkpoint_writes"

    thread_id = Column(String, primary_key=True)
    checkpoint_ns = Column(String, primary_key=True, default='')
    checkpoint_id = Column(String, primary_key=True)
    task_id = Column(String, primary_key=True)
    idx = Column(Integer, primary_key=True)

    channel = Column(String, nullable=False)
    type = Column(String, nullable=True)
    blob = Column(LargeBinary, nullable=False)
    task_path = Column(String, nullable=False, default='')


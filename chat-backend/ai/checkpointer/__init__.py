import os
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

_checkpointer = None
_pool = None

async def init_checkpointer(type: str = "memory"):
    global _checkpointer, _pool

    if type == "postgres":
        db_url = os.getenv("CHECKPOINT_DB_URL")
        if not db_url:
            raise ValueError("CHECKPOINT_DB_URL 환경변수가 필요합니다")

        _pool = AsyncConnectionPool(
            conninfo=db_url,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0}
        )
        _checkpointer = AsyncPostgresSaver(_pool)
        await _checkpointer.setup()

    else:
        _checkpointer = InMemorySaver()

async def close_checkpointer():
    if _pool:
        await _pool.close()

def get_checkpointer():
    return _checkpointer
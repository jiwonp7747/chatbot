import logging

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.checkpoint_models import CheckPoint

logger = logging.getLogger("checkpoint")

async def get_checkpoints_by_thread_id(
        thread_id,
        db: AsyncSession,
):
    query = (select(CheckPoint).where(CheckPoint.thread_id == thread_id)
             .order_by(desc(CheckPoint.checkpoint_id)))
    result = await db.execute(query)
    return result.scalars().all()
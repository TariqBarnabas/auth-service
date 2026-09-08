from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import AuditEvent


async def log_audit_event(
    session: AsyncSession,
    event_type: str,
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
):
    session.add(AuditEvent(user_id=user_id, event_type=event_type, ip_address=ip_address))
    await session.commit()


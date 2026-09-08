from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.dependencies import require_admin
from app.models.db import RefreshToken

router = APIRouter()


@router.post("/users/{user_id}/revoke-sessions", status_code=204)
async def revoke_user_sessions(
    user_id: UUID,
    admin: dict = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await session.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )
    await session.commit()
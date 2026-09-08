from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token,
)
from app.core.rate_limit import enforce_rate_limit, is_account_locked, record_failed_login, clear_failed_logins
from app.core.audit import log_audit_event
from app.core.logging_config import logger
from app.models.db import User, RefreshToken
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserPublic, RefreshRequest, PasswordResetRequest, PasswordResetConfirm
from app.dependencies import get_current_user
from app.core.email import email_sender
from app.core.redis import redis_client

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=201)
async def register(payload: RegisterRequest, request: Request, session: AsyncSession = Depends(get_session)):
    await enforce_rate_limit(f"ratelimit:register:{request.client.host}", max_requests=5, window_seconds=60)

    new_user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role="user",
    )
    session.add(new_user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    await session.refresh(new_user)
    logger.info(f"New user registered: {new_user.id}")
    return new_user


async def _issue_tokens(user: User, session: AsyncSession) -> TokenResponse:
    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, refresh_hash = generate_refresh_token()
    session.add(RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        family_id=uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
    ))
    await session.commit()
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)):
    email = payload.email.lower()
    await enforce_rate_limit(f"ratelimit:login:{email}", max_requests=10, window_seconds=60)

    invalid_credentials = HTTPException(status_code=401, detail="Invalid email or password")

    if await is_account_locked(email):
        # Same error as wrong credentials — confirming "this account is locked"
        # would itself leak that the account exists.
        raise invalid_credentials

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(user.password_hash, payload.password):
        await record_failed_login(email)
        await log_audit_event(session, "login_failure", user_id=(user.id if user else None), ip_address=request.client.host)
        logger.info(f"Failed login attempt for {email}")
        raise invalid_credentials

    await clear_failed_logins(email)
    await log_audit_event(session, "login_success", user_id=user.id, ip_address=request.client.host)
    logger.info(f"Successful login: {user.id}")
    return await _issue_tokens(user, session)


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.id == UUID(current_user["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: AsyncSession = Depends(get_session)):
    incoming_hash = hash_token(payload.refresh_token)
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == incoming_hash))
    token_row = result.scalar_one_or_none()

    reject = HTTPException(status_code=401, detail="Invalid refresh token")
    if token_row is None:
        raise reject

    if token_row.revoked:
        await session.execute(
            update(RefreshToken).where(RefreshToken.family_id == token_row.family_id).values(revoked=True)
        )
        await session.commit()
        await log_audit_event(session, "token_reuse_detected", user_id=token_row.user_id)
        logger.warning(f"Refresh token reuse detected for user {token_row.user_id}")
        raise reject

    if datetime.now(timezone.utc) > token_row.expires_at:
        raise reject

    token_row.revoked = True
    await session.commit()

    result = await session.execute(select(User).where(User.id == token_row.user_id))
    user = result.scalar_one_or_none()
    return await _issue_tokens(user, session)


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, session: AsyncSession = Depends(get_session)):
    incoming_hash = hash_token(payload.refresh_token)
    result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == incoming_hash))
    token_row = result.scalar_one_or_none()
    if token_row is not None:
        await session.execute(
            update(RefreshToken).where(RefreshToken.family_id == token_row.family_id).values(revoked=True)
        )
        await session.commit()
        await log_audit_event(session, "logout", user_id=token_row.user_id)


@router.post("/logout-all", status_code=204)
async def logout_all(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    user_id = UUID(current_user["sub"])
    await session.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )
    await session.commit()
    await log_audit_event(session, "logout_all", user_id=user_id)

@router.post("/password-reset/request", status_code=202)
async def request_password_reset(payload: PasswordResetRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user is not None:
        raw_token = secrets.token_urlsafe(32)
        await redis_client.set(f"password_reset:{raw_token}", str(user.id), ex=900)  # 15 minutes
        reset_link = f"https://your-frontend.example/reset-password?token={raw_token}"
        await email_sender.send(to=user.email, subject="Password Reset", body=f"Reset link: {reset_link}")

    # Same response whether or not the account exists — same enumeration-protection
    # principle as login.
    return {"message": "If an account exists for this email, a reset link has been sent."}


@router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(payload: PasswordResetConfirm, session: AsyncSession = Depends(get_session)):
    user_id_str = await redis_client.get(f"password_reset:{payload.token}")
    if user_id_str is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user_id = UUID(user_id_str)
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.password_hash = hash_password(payload.new_password)
    await redis_client.delete(f"password_reset:{payload.token}")

    # A password reset kills every existing session, not just this device.
    await session.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )
    await session.commit()
    await log_audit_event(session, "password_change", user_id=user_id)
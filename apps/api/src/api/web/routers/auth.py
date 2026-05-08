"""``/v1/auth/*`` — signup + login.

Tokens are HS256 JWTs from ``api.web.security`` with ``sub=user_id``.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import models as orm
from api.web.deps import get_db
from api.web.security import hash_password, issue_token, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    name: str | None = None
    language: str = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: str


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = (
        await db.execute(select(orm.User).where(orm.User.email == req.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")
    user = orm.User(
        id=f"u_{uuid4().hex[:12]}",
        email=req.email,
        name=req.name,
        language=req.language if req.language in ("en", "hi") else "en",
        password_hash=hash_password(req.password),
    )
    db.add(user)
    await db.commit()
    return TokenResponse(token=issue_token(user.id), user_id=user.id)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = (
        await db.execute(select(orm.User).where(orm.User.email == req.email))
    ).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return TokenResponse(token=issue_token(user.id), user_id=user.id)

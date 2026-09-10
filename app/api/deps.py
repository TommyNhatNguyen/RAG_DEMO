from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.config.settings import Settings
from app.factory import AppServices


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_services(request: Request) -> AppServices:
    return request.app.state.services


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    expected = request.app.state.settings.api_key
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

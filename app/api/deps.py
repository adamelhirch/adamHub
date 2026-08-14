from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.core.auth import (
    resolve_current_or_owner_user,
    resolve_optional_user,
    resolve_user_from_request,
)
from app.core.db import get_session
from app.core.security import require_api_key
from app.models import User

SessionDep = Annotated[Session, Depends(get_session)]
ApiKeyDep = Annotated[None, Depends(require_api_key)]


def _current_user_dep(request: Request, session: SessionDep) -> User:
    return resolve_user_from_request(request, session)


def _optional_user_dep(request: Request, session: SessionDep) -> User | None:
    return resolve_optional_user(request, session)


def _current_or_owner_user_dep(request: Request, session: SessionDep) -> User:
    return resolve_current_or_owner_user(request, session)


CurrentUser = Annotated[User, Depends(_current_user_dep)]
OptionalUser = Annotated[User | None, Depends(_optional_user_dep)]
# Mandatory acting user for the multi-tenant domain routers: a valid JWT Bearer
# token resolves to that user, otherwise a valid shared X-API-Key resolves to
# the ADAMHUB_OWNER_EMAIL user, otherwise 401. Never optional.
CurrentOrOwnerUser = Annotated[User, Depends(_current_or_owner_user_dep)]

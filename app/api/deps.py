from typing import Annotated

from fastapi import Depends, Request
from sqlmodel import Session

from app.core.auth import resolve_optional_user, resolve_user_from_request
from app.core.db import get_session
from app.core.security import require_api_key
from app.models import User

SessionDep = Annotated[Session, Depends(get_session)]
ApiKeyDep = Annotated[None, Depends(require_api_key)]


def _current_user_dep(request: Request, session: SessionDep) -> User:
    return resolve_user_from_request(request, session)


def _optional_user_dep(request: Request, session: SessionDep) -> User | None:
    return resolve_optional_user(request, session)


CurrentUser = Annotated[User, Depends(_current_user_dep)]
OptionalUser = Annotated[User | None, Depends(_optional_user_dep)]

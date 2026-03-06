from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.core.db import get_session
from app.core.security import require_api_key

SessionDep = Annotated[Session, Depends(get_session)]
ApiKeyDep = Annotated[None, Depends(require_api_key)]

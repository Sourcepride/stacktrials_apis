# Shared dependencies for routes


from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlmodel import Session

from .database import create_app_db_engine

engine = create_app_db_engine()


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

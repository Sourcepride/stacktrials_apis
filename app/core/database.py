from sqlmodel import create_engine

from app.common.constants import DATABASE_URI

# DB connection, session


def create_app_db_engine():
    return create_engine(DATABASE_URI)

import json
import random
import string

from sqlmodel import Session, select

from app.models.user_model import Account


def generate_random_username(session: Session, name: str, addons: int = 8) -> str:
    while True:
        username = f"{name}@" + "".join(
            random.choices(string.ascii_lowercase + string.digits, k=addons)
        )
        username_exists = session.exec(
            select(Account).where(Account.username == username)
        ).first()

        if not username_exists:
            return username


def safe_json_loads(data, default=None):
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default

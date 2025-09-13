import base64
import hashlib
import json
import random
import re
import string
import unicodedata
from typing import Any, List, Optional, TypeVar, Union
from urllib.parse import urljoin, urlparse

from cryptography.fernet import Fernet
from sqlalchemy import Select, func
from sqlmodel import Session, SQLModel, select

from app.common.constants import PER_PAGE, SECRET_KEY
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


T = TypeVar("T", bound=SQLModel)


def paginate(
    session: Session,
    selected_model: Union[type[T], Select],
    page: int = 1,
    per_page: int = PER_PAGE,
) -> dict[str, Any]:
    """
    Generic paginator.
    - selected_model may be a SQLModel class (e.g. User) or an existing select(...) query.
    - Returns dict with items, total, page, per_page, total_pages.
    """
    # Handle both SQLModel classes and existing queries
    if isinstance(selected_model, type) and issubclass(selected_model, SQLModel):
        # It's a SQLModel class, create a select query
        query = select(selected_model)
    else:
        # It's already a query (Select object)
        query = selected_model

    # Validate pagination parameters
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20

    # Calculate offset
    offset = (page - 1) * per_page

    # Get paginated items
    paginated_query = query.offset(offset).limit(per_page)
    items: List[T] = session.exec(paginated_query).all()  # type: ignore

    # Get total count
    try:
        # Create count query from the original query
        if hasattr(query, "subquery"):
            # For complex queries, use subquery approach
            count_query = select(func.count()).select_from(query.subquery())
        else:
            # For simple queries, count the table directly
            count_query = select(func.count()).select_from(query.froms[0])

        total = session.exec(count_query).one()
    except Exception as e:
        # Fallback: try a simpler count approach
        try:
            # Remove offset/limit and count
            base_query = query.offset(None).limit(None)
            total = len(session.exec(base_query).all())  # type: ignore
        except Exception:
            # Final fallback: use length of current items
            total = len(items)

    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def slugify(data: str, max_length: Optional[int] = None) -> str:
    """
    Create a URL-safe slug.

    - Normalize Unicode to ASCII.
    - Lowercase, trim.
    - Replace whitespace/underscores with hyphens.
    - Remove non-alphanumeric/hyphen characters.
    - Collapse multiple hyphens and trim leading/trailing hyphens.
    - Optionally truncate to max_length (without leaving trailing hyphen).
    - Returns "n-a" if result is empty.
    """
    if not data:
        return "n-a"

    # Normalize unicode and remove non-ascii
    s = unicodedata.normalize("NFKD", data)
    s = s.encode("ascii", "ignore").decode("ascii")

    s = s.lower().strip()
    s = re.sub(r"[\s_]+", "-", s)  # spaces/underscores -> hyphen
    s = re.sub(r"[^a-z0-9\-]", "", s)  # remove invalid chars
    s = re.sub(r"-{2,}", "-", s)  # collapse multiple hyphens
    s = s.strip("-")

    if max_length and max_length > 0:
        s = s[:max_length].rstrip("-")

    return s or "n-a"


def encode_state(data: dict[str, Any]) -> str:
    """Encode state data as a base64 JSON string"""
    json_str = json.dumps(data)
    encoded = base64.urlsafe_b64encode(json_str.encode()).decode()
    return encoded


def decode_state(state: str) -> dict[str, Any]:
    """Decode state data from base64 JSON string"""
    try:
        json_str = base64.urlsafe_b64decode(state.encode()).decode()
        return json.loads(json_str)
    except Exception:
        return {}


def extract_redirect_uri(redirect: str, base_url: str):
    url = urlparse(redirect)
    redirect = urljoin(base_url, url.path) + f"?={url.query}"
    if url.fragment:
        return redirect + f"#{url.fragment}"

    return redirect


def accepted_mime():
    pass

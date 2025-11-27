import json
from functools import lru_cache
from pathlib import Path

from app.i18n.translation import Language

from .config import settings

base_path = Path(__file__).resolve().parent / "locales"


@lru_cache(maxsize=None)
def translation(lang: str = "") -> Language:
    locale = settings.default_locale
    if lang in settings.supported_locale:
        locale = lang

    try:
        file_path = base_path / locale / "translations.json"
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    return Language(lang, data)

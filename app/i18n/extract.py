import json
import os
import re
from pathlib import Path

from genericpath import isfile

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCALES_DIR = Path(__file__).resolve().parent / "locales"
SOURCE_LANG = "en"
SOURCE_FILE = LOCALES_DIR / SOURCE_LANG / "translations.json"

TRANSLATION_KEY_REGEX = re.compile(r"trans\.t\([\"']([\w\.\-]+)[\"']\)")


def find_translation_keys():
    keys = set()

    for root, _, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith(".py"):
                path = Path(root) / file
                text = path.read_text()

                found = TRANSLATION_KEY_REGEX.findall(text)
                keys.update(found)

    return sorted(keys)


def insert_key(container, key_parts):
    part = key_parts[0]

    if len(key_parts) == 1:
        if part not in container:
            container[part] = "__FILL_ME__"
        return

    if part not in container or not isinstance(container[part], dict):
        container[part] = {}

    insert_key(container[part], key_parts[1:])


def main():
    print("🔍 Extracting translation keys from source code…")

    keys = find_translation_keys()
    print(f"→ Found {len(keys)} translation keys.")

    if SOURCE_FILE.exists():
        src_dict = json.loads(SOURCE_FILE.read_text())
    else:
        src_dict = {}

    for k in keys:
        insert_key(src_dict, k.split("."))

    SOURCE_FILE.write_text(json.dumps(src_dict, indent=2, ensure_ascii=False))
    print(f"✨ Updated source locale: {SOURCE_FILE}")


if __name__ == "__main__":
    main()

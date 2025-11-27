import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOCALES_DIR = BASE_DIR / "locales"
SOURCE_LANG = "en"
SOURCE_FILE = LOCALES_DIR / SOURCE_LANG / "translations.json"


def load_json(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_json(path: Path, content: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2))


def sync_dict(source: dict, target: dict, lang: str, prefix=""):
    updated = False
    missing = []
    extra = []

    for key, src_val in source.items():
        full_key = f"{prefix}{key}"
        if isinstance(src_val, dict):
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                updated = True

            u, m, e = sync_dict(src_val, target[key], lang, full_key + ".")
            updated |= u
            missing.extend(m)
            extra.extend(e)
        else:
            if key not in target:
                target[key] = ""
                updated = True
                missing.append(full_key)

    for k in list(target.keys()):
        if k not in source:
            del target[k]
            updated = True
            extra.append(prefix + k)

    return updated, missing, extra


def main():
    print("🔄 Syncing translations…")

    source_dict = load_json(SOURCE_FILE)

    for lang_folder in LOCALES_DIR.iterdir():
        if not lang_folder.is_dir():
            continue

        lang = lang_folder.name
        target_file = lang_folder / "translations.json"

        if lang == SOURCE_LANG:
            print(f"✓ {lang} is the source locale, skipping.")
            continue

        print(f"\n→ Syncing '{lang}'…")

        target_dict = load_json(target_file)
        updated, missing_keys, extra_keys = sync_dict(source_dict, target_dict, lang)

        if updated:
            save_json(target_file, target_dict)
            print(f"  ✔ Updated {lang}")

        if missing_keys:
            print(f"  ⚠ Missing keys ({len(missing_keys)}):")
            for k in missing_keys:
                print(f"    - {k}")

        if extra_keys:
            print(f"  ⚠ Extra keys removed ({len(extra_keys)}):")
            for k in extra_keys:
                print(f"    - {k}")

    print("\n✨ Sync complete!")


if __name__ == "__main__":
    main()

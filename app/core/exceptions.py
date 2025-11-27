# Custom exception handlers
import json
import logging
import logging.config
import os
from pathlib import Path


def expand_env(obj):
    if isinstance(obj, dict):
        return {k: expand_env(v) for k, v in obj.items()}

    elif isinstance(obj, list):
        return [expand_env(i) for i in obj]

    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        expr = obj[2:-1]

        # Support default values: ${VAR:DEFAULT}
        if ":" in expr:
            name, default = expr.split(":", 1)
            return os.getenv(name, default)

        # No default → safe fallback is empty string (so app doesn't crash)
        return os.getenv(expr, "")

    return obj


def setup_logger():
    try:
        config_path = Path(__file__).resolve().parent.parent.parent / "logging.json"
        with open(config_path) as f:
            raw = json.load(f)

        config = expand_env(raw)

        # Safe configure: never crash app on logging config error
        logging.config.dictConfig(config)

        return logging.getLogger("app")

    except Exception as e:
        # Fallback basic logger
        print("\n================ LOGGING SETUP ERROR ================\n")
        print(f"Error while loading logging.json: {e}\n")
        print("Falling back to basic console logger...\n")
        print("=====================================================\n")

        fallback = logging.getLogger("app")
        fallback.setLevel(logging.INFO)

        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        fallback.addHandler(handler)
        fallback.error(f"Failed to load logging config. Using fallback. Error: {e}")

        return fallback

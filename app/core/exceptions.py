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
        return os.getenv(obj[2:-1])
    else:
        return obj


def setup_logger():
    logging_file_path = (
        Path(__file__).resolve().parent.parent.parent.joinpath("logging.json")
    )

    with open(logging_file_path) as f:
        conf = json.loads(f.read())

    logging.config.dictConfig(expand_env(conf))
    app_logger = logging.getLogger("app")

    # console_logger = logging.StreamHandler(sys.stdout)
    # console_logger.setLevel(logging.INFO)

    # app_logger.addHandler(console_logger)

    # app_logger.propagate = False
    return app_logger

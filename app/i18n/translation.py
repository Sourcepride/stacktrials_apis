from typing import Any


class Language:
    def __init__(self, lang_code: str, data: Any):
        self.lang_code = lang_code
        self.data = data

    def t(self, key: str, **kwargs):
        lookups = key.split(".")
        value = self.data

        for param in lookups:
            if not isinstance(value, dict) or param not in value:
                value = key
                break
            value = value[param]

        if not isinstance(value, str):
            value = key

        for k, v in kwargs.items():
            replace_text = f"{{{k}}}"
            value = value.replace(replace_text, str(v))

        return value

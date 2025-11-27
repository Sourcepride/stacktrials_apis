from pydantic_settings import BaseSettings


class LangConfig(BaseSettings):
    supported_locale: list[str] = ["en", "es", "de", "fr"]
    default_locale: str = "en"

    class Config:
        env_prefix = "LOCALE_"


settings = LangConfig()

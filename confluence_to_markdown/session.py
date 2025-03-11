from atlassian import Confluence
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):
    username: str = Field()
    password: str = Field()
    url: str = Field()

    model_config = SettingsConfigDict(env_file=".env")


def get_session() -> Confluence:
    settings = Settings()  # type: ignore reportCallIssue as the parameters are read via env file

    return Confluence(
        url=settings.url,
        username=settings.username,
        password=settings.password,
    )

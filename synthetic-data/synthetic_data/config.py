"""Runtime config loaded from env vars."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pg_host: str = Field("localhost", alias="POSTGRES_HOST")
    pg_port: int = Field(5432, alias="POSTGRES_PORT")
    pg_db: str = Field("api_analytics", alias="POSTGRES_DB")
    pg_user: str = Field("api_analytics", alias="POSTGRES_USER")
    pg_password: str = Field("change_me_locally", alias="POSTGRES_PASSWORD")

    @property
    def dsn(self) -> str:
        return (
            f"host={self.pg_host} port={self.pg_port} "
            f"dbname={self.pg_db} user={self.pg_user} password={self.pg_password}"
        )


settings = Settings()

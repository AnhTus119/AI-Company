"""Machine-specific runtime settings; story and policy rules stay shared."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping

from sqlalchemy.engine import URL

from ai_company.domain.workflow import DomainError


class RuntimeProfile(StrEnum):
    LITE = "lite"
    STANDARD = "standard"


@dataclass(frozen=True)
class RuntimeSettings:
    profile: RuntimeProfile
    database_url: str
    data_dir: Path | None
    transport: str
    max_local_workers: int | None


def default_data_dir(environment: Mapping[str, str]) -> Path:
    configured = environment.get("AI_COMPANY_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    local_app_data = environment.get("LOCALAPPDATA")
    if local_app_data:
        return (Path(local_app_data) / "AIContentCompany").resolve()
    return (Path.home() / ".local" / "share" / "ai-content-company").resolve()


def load_runtime_settings(environment: Mapping[str, str] | None = None) -> RuntimeSettings:
    values = os.environ if environment is None else environment
    try:
        profile = RuntimeProfile(values.get("AI_COMPANY_PROFILE", "lite").lower())
    except ValueError as exc:
        raise DomainError("AI_COMPANY_PROFILE must be 'lite' or 'standard'.") from exc

    if profile == RuntimeProfile.LITE:
        data_dir = default_data_dir(values)
        database_url = URL.create(
            "sqlite+pysqlite", database=str(data_dir / "state.sqlite3")
        ).render_as_string(hide_password=False)
        return RuntimeSettings(profile, database_url, data_dir, "database_polling", 1)

    database_url = values.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql+"):
        raise DomainError("The standard profile requires a PostgreSQL DATABASE_URL.")
    if not values.get("RABBITMQ_URL", "").startswith("amqp"):
        raise DomainError("The standard profile requires a RabbitMQ URL.")
    return RuntimeSettings(profile, database_url, None, "rabbitmq", None)

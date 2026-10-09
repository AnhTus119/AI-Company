"""Load a local .env without adding a dependency or overriding process settings."""

from __future__ import annotations

import os
from pathlib import Path


ALLOWED_LOCAL_KEYS = frozenset({
    "AI_COMPANY_PROFILE",
    "AI_COMPANY_DATA_DIR",
    "ARTIFACT_ROOT",
    "AI_COMPANY_REAL_AI_ENABLED",
    "AI_COMPANY_POLICY_VERSION",
    "AI_COMPANY_ASSIGNMENT_VERSION",
    "AI_COMPANY_BUDGET_VERSION",
    "AI_COMPANY_DAILY_BUDGET_MINOR",
    "AI_COMPANY_BUDGET_CURRENCY",
    "AI_COMPANY_GEMINI_RATE_CARD_VERSION",
    "AI_COMPANY_GEMINI_INPUT_MINOR_PER_MILLION",
    "AI_COMPANY_GEMINI_OUTPUT_MINOR_PER_MILLION",
    "AI_COMPANY_GEMINI_MAX_OUTPUT_TOKENS",
    "AI_COMPANY_GEMINI_TIMEOUT_SECONDS",
    "GEMINI_MODEL",
    "GEMINI_API_KEY",
})


def load_local_env(path: Path) -> None:
    if not path.is_file():
        return
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env entry on line {line_number}.")
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_LOCAL_KEYS:
            raise ValueError(f"Unsupported .env setting on line {line_number}: {key}.")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'\"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)

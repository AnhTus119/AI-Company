"""Manual Lite database snapshot; destination must be chosen by the operator."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_company.application.lite_backup import backup_lite_database
from ai_company.application.runtime import RuntimeProfile, load_runtime_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the Lite SQLite database")
    parser.add_argument("destination", type=Path, help="New .sqlite3 backup file; parent directory must exist")
    args = parser.parse_args()
    settings = load_runtime_settings()
    if settings.profile != RuntimeProfile.LITE or settings.data_dir is None:
        parser.error("This command supports the Lite profile only.")
    source = settings.data_dir / "state.sqlite3"
    result = backup_lite_database(source, args.destination)
    print(f"Verified database snapshot: {result}")


if __name__ == "__main__":
    main()

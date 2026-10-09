"""Consistent, non-overwriting snapshot of a Lite SQLite database."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path


def backup_lite_database(source: Path, destination: Path) -> Path:
    # Windows may deny realpath resolution while SQLite has an open WAL handle.
    source = source.absolute()
    destination = destination.absolute()
    if not source.is_file() or source.suffix != ".sqlite3":
        raise ValueError("Source must be an existing Lite SQLite database.")
    if destination == source:
        raise ValueError("Backup destination must differ from the source database.")
    if not destination.parent.is_dir():
        raise ValueError("Backup destination directory must already exist.")

    # Exclusive creation prevents accidental replacement of an earlier snapshot.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as live:
            with closing(sqlite3.connect(destination)) as snapshot:
                live.backup(snapshot)
                if snapshot.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise ValueError("The backup has an unsupported Lite schema version.")
                if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("The backup failed SQLite integrity validation.")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination

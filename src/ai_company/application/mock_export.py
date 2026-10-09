"""Atomic five-file mock export for storage and checksum tests.

Media validity and creative quality are separate gates. This module only
copies already-created mock source files into the version-one layout.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Mapping
from uuid import UUID

from ai_company.domain.workflow import ArtifactEvidence, KPI_TIMEZONE, REQUIRED_ARTIFACTS


@dataclass(frozen=True)
class MockExportResult:
    directory: Path
    evidence: dict[str, ArtifactEvidence]


def _digest_file(path: Path) -> tuple[str, int]:
    digest = sha256()
    total = 0
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
            total += len(block)
    return digest.hexdigest(), total


def mock_export_destination(output_root: Path, story_id: UUID, title: str, at: datetime) -> Path:
    if at.tzinfo is None:
        raise ValueError("Export timestamp must include a timezone.")
    if not title.strip():
        raise ValueError("A mock export needs a story title.")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].rstrip("-") or "untitled"
    date_label = at.astimezone(KPI_TIMEZONE).date().isoformat()
    return output_root / "MOCK_OUTPUT" / f"{date_label}__STORY-{story_id}__{slug}"


def inspect_existing_mock_export(directory: Path) -> MockExportResult:
    if not directory.is_dir() or {item.name for item in directory.iterdir()} != REQUIRED_ARTIFACTS:
        raise ValueError("Existing mock export is incomplete or has unexpected files.")
    evidence = {}
    for filename in REQUIRED_ARTIFACTS:
        path = directory / filename
        if not path.is_file() or path.is_symlink():
            raise ValueError("Existing mock export has an invalid file.")
        digest, size = _digest_file(path)
        if size <= 0:
            raise ValueError("Existing mock export has an empty file.")
        evidence[filename] = ArtifactEvidence(filename, digest, size, True, True)
    return MockExportResult(directory, evidence)


def verified_mock_artifact(
    output_root: Path, story_id: UUID, directory: str, filename: str, artifacts: dict,
) -> Path:
    """Resolve one published mock file under the configured root and verify its evidence."""
    if filename not in REQUIRED_ARTIFACTS:
        raise ValueError("Unknown mock artifact.")
    expected = artifacts.get(filename)
    if not isinstance(expected, dict) or expected.get("is_mock") is not True or expected.get("verified") is not True:
        raise ValueError("Mock artifact evidence is missing.")
    # Windows/OneDrive may deny realpath for an otherwise readable directory.
    # Compare normalized absolute paths, then reject link/junction escapes.
    root = Path(os.path.abspath(output_root / "MOCK_OUTPUT"))
    candidate = Path(directory)
    if candidate.is_symlink() or candidate.is_junction() or not candidate.is_dir():
        raise ValueError("Mock package directory is invalid.")
    package = Path(os.path.abspath(candidate))
    if package.parent != root or f"__STORY-{story_id}__" not in package.name:
        raise ValueError("Mock package is outside the expected story directory.")
    path = package / filename
    if path.is_symlink() or not path.is_file():
        raise ValueError("Mock artifact file is invalid.")
    digest, size = _digest_file(path)
    if digest != expected.get("sha256") or size != expected.get("byte_size"):
        raise ValueError("Mock artifact integrity check failed.")
    return path


def export_mock_package(
    output_root: Path,
    story_id: UUID,
    title: str,
    sources: Mapping[str, Path],
    *,
    at: datetime,
) -> MockExportResult:
    """Stage, verify, and publish mock files without replacing an old export."""
    if set(sources) != REQUIRED_ARTIFACTS:
        raise ValueError("A mock export needs exactly the five v1 files.")
    for path in sources.values():
        if not path.is_file() or path.is_symlink():
            raise ValueError("Each mock source must be a regular file.")
    root = output_root / "MOCK_OUTPUT"
    root.mkdir(parents=True, exist_ok=True)
    destination = mock_export_destination(output_root, story_id, title, at)
    if destination.exists():
        raise FileExistsError(f"Mock export already exists: {destination}")

    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=root))
    evidence: dict[str, ArtifactEvidence] = {}
    try:
        for filename in sorted(REQUIRED_ARTIFACTS):
            target = staging / filename
            with sources[filename].open("rb") as source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            source_digest, source_size = _digest_file(sources[filename])
            target_digest, target_size = _digest_file(target)
            if source_size <= 0 or (source_digest, source_size) != (target_digest, target_size):
                raise ValueError(f"Mock artifact copy failed integrity validation: {filename}")
            evidence[filename] = ArtifactEvidence(
                filename, target_digest, target_size, verified=True, is_mock=True,
            )
        if destination.exists():
            raise FileExistsError(f"Mock export already exists: {destination}")
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return MockExportResult(destination, evidence)

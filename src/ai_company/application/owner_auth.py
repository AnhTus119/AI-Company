"""Two-owner local credentials; never store plaintext passwords in source or SQLite."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path


OWNERS = ("Tou", "Chibun")
AUTH_FILENAME = "owner_auth.json"


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt-16384-8-1:{_encode(salt)}:{_encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_text, digest_text = stored.split(":")
        if scheme != "scrypt-16384-8-1":
            return False
        expected = _decode(digest_text)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=_decode(salt_text), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


@dataclass(frozen=True)
class OwnerAuth:
    users: dict[str, str]
    session_secret: str
    public_ready: bool = False

    def authenticate(self, username: str, password: str) -> bool:
        stored = self.users.get(username)
        # Keep a password-hash check even for an unknown username.
        return verify_password(password, stored or self.users[OWNERS[0]]) and stored is not None


def load_owner_auth(data_dir: Path) -> OwnerAuth:
    path = data_dir / AUTH_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Owner access is not configured. Run the local launcher to set it up.") from exc
    users = payload.get("users") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(users, dict) or set(users) != set(OWNERS) or not all(isinstance(value, str) for value in users.values()):
        raise RuntimeError("Owner access file is invalid; only Tou and Chibun are allowed.")
    secret = payload.get("session_secret")
    if not isinstance(secret, str) or len(secret) < 40:
        raise RuntimeError("Owner session secret is invalid.")
    return OwnerAuth(users, secret, bool(payload.get("public_ready", False)))


def create_owner_auth(data_dir: Path, passwords: dict[str, str], *, allow_weak_local: bool = False) -> Path:
    if set(passwords) != set(OWNERS):
        raise ValueError("Exactly two owner accounts are required.")
    if not allow_weak_local and any(len(value) < 12 for value in passwords.values()):
        raise ValueError("Use at least 12 characters per password before public deployment.")
    if any(not value for value in passwords.values()):
        raise ValueError("Passwords cannot be empty.")
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / AUTH_FILENAME
    payload = {
        "schema_version": 1,
        "users": {name: hash_password(passwords[name]) for name in OWNERS},
        "session_secret": _encode(secrets.token_bytes(32)),
        "public_ready": False,
    }
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def ensure_prototype_owner_auth(data_dir: Path, password: str) -> Path:
    """Install the two user-requested demo accounts, migrating the former account file once."""
    path = data_dir / AUTH_FILENAME
    if path.exists():
        try:
            current = load_owner_auth(data_dir)
        except RuntimeError:
            pass
        else:
            if all(current.authenticate(name, password) for name in OWNERS):
                return path

    if not path.exists():
        return create_owner_auth(data_dir, {name: password for name in OWNERS}, allow_weak_local=True)

    backup = data_dir / f"owner_auth.previous-{secrets.token_hex(6)}.json"
    os.replace(path, backup)
    try:
        return create_owner_auth(data_dir, {name: password for name in OWNERS}, allow_weak_local=True)
    except BaseException:
        if not path.exists():
            os.replace(backup, path)
        raise

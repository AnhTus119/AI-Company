"""First-run interactive local credential setup."""

from __future__ import annotations

import argparse
import getpass

from ai_company.application.owner_auth import OWNERS, create_owner_auth
from ai_company.application.runtime import RuntimeProfile, load_runtime_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Set the two local owner passwords")
    parser.add_argument("--allow-weak-local", action="store_true", help="Allow short passwords for localhost only")
    args = parser.parse_args()
    settings = load_runtime_settings()
    if settings.profile != RuntimeProfile.LITE or settings.data_dir is None:
        parser.error("This setup command supports the local Lite profile only.")
    passwords = {}
    for name in OWNERS:
        first = getpass.getpass(f"New password for {name}: ")
        second = getpass.getpass(f"Repeat password for {name}: ")
        if first != second:
            parser.error("Passwords did not match.")
        passwords[name] = first
    path = create_owner_auth(settings.data_dir, passwords, allow_weak_local=args.allow_weak_local)
    print(f"Two owner accounts configured at {path}. Passwords were not stored in plaintext.")


if __name__ == "__main__":
    main()

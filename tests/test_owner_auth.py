import pytest

import json

from ai_company.application.owner_auth import create_owner_auth, ensure_prototype_owner_auth, load_owner_auth


def test_two_owner_passwords_are_hashed_and_file_is_not_overwritten(tmp_path) -> None:
    path = create_owner_auth(tmp_path, {
        "Tou": "a-long-local-password", "Chibun": "a-different-long-password",
    })
    contents = path.read_text(encoding="utf-8")
    assert "a-long-local-password" not in contents
    assert "a-different-long-password" not in contents
    config = load_owner_auth(tmp_path)
    assert config.authenticate("Tou", "a-long-local-password")
    assert config.authenticate("Chibun", "a-different-long-password")
    assert not config.authenticate("Tou", "incorrect")
    assert not config.authenticate("Other", "a-long-local-password")
    with pytest.raises(FileExistsError):
        create_owner_auth(tmp_path, {"Tou": "another-long-password", "Chibun": "another-long-password"})


def test_prototype_owner_auth_migrates_old_accounts_without_losing_previous_file(tmp_path) -> None:
    old = create_owner_auth(tmp_path, {"Tou": "old-long-password", "Chibun": "another-old-long-password"})
    payload = json.loads(old.read_text(encoding="utf-8"))
    payload["users"]["Atus"] = payload["users"].pop("Tou")
    old.write_text(json.dumps(payload), encoding="utf-8")
    ensure_prototype_owner_auth(tmp_path, "trial-password")
    current = load_owner_auth(tmp_path)
    assert current.authenticate("Tou", "trial-password")
    assert current.authenticate("Chibun", "trial-password")
    assert not current.authenticate("Atus", "trial-password")
    assert len(list(tmp_path.glob("owner_auth.previous-*.json"))) == 1
    ensure_prototype_owner_auth(tmp_path, "trial-password")
    assert len(list(tmp_path.glob("owner_auth.previous-*.json"))) == 1


def test_prototype_owner_auth_resets_password_when_local_secret_changes(tmp_path) -> None:
    create_owner_auth(tmp_path, {"Tou": "old-long-password", "Chibun": "another-old-long-password"})
    ensure_prototype_owner_auth(tmp_path, "new-demo-password")
    current = load_owner_auth(tmp_path)
    assert current.authenticate("Tou", "new-demo-password")
    assert current.authenticate("Chibun", "new-demo-password")
    assert len(list(tmp_path.glob("owner_auth.previous-*.json"))) == 1


def test_local_app_factory_starts_with_two_owner_auth(tmp_path, monkeypatch) -> None:
    from ai_company.api.main import create_app

    monkeypatch.setenv("AI_COMPANY_PROFILE", "lite")
    monkeypatch.setenv("AI_COMPANY_DATA_DIR", str(tmp_path))
    ensure_prototype_owner_auth(tmp_path, "new-demo-password")
    app = create_app()
    assert any(route.path == "/login" for route in app.routes)
    assert any(route.path == "/health" for route in app.routes)

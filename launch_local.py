"""One-command local Lite launcher; uses the same Python for API and worker."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
REQUIRED = ("fastapi", "uvicorn", "pydantic", "sqlalchemy", "itsdangerous", "imageio_ffmpeg", "PIL")


def ensure_dependencies() -> None:
    missing = [name for name in REQUIRED if importlib.util.find_spec(name) is None]
    if not missing:
        return
    if os.environ.get("AI_COMPANY_BOOTSTRAP_ATTEMPTED") == "1":
        raise RuntimeError("Thu vien van thieu sau khi cai. Kiem tra loi pip o phia tren.")
    print("Dang cai thu vien con thieu cho ban Lite...", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".[media]"],
        cwd=ROOT, check=True,
    )
    # A fresh interpreter sees newly installed user-site packages. Keep this one click.
    print("Da cai xong. Dang tiep tuc khoi dong...", flush=True)
    os.environ["AI_COMPANY_BOOTSTRAP_ATTEMPTED"] = "1"
    os.execv(sys.executable, [sys.executable, str(ROOT / "launch_local.py"), *sys.argv[1:]])


def healthy(url: str) -> bool:
    try:
        with urlopen(url + "/health", timeout=1) as response:
            return json.load(response) == {"status": "ok"}
    except (URLError, TimeoutError, ValueError):
        return False


def login_available(url: str) -> bool:
    try:
        with urlopen(url + "/login", timeout=1) as response:
            return response.status == 200
    except (URLError, TimeoutError):
        return False


def ensure_owner_access(environment: dict[str, str]) -> Path:
    sys.path.insert(0, str(ROOT / "src"))
    from ai_company.application.owner_auth import ensure_prototype_owner_auth
    from ai_company.application.runtime import default_data_dir

    data_dir = default_data_dir(environment)
    password = environment.get("AI_COMPANY_DEMO_PASSWORD")
    if not password:
        local_secrets = ROOT / ".env"
        if local_secrets.is_file():
            for line in local_secrets.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "AI_COMPANY_DEMO_PASSWORD":
                    password = value.strip()
                    break
    if not password:
        raise RuntimeError("Thieu AI_COMPANY_DEMO_PASSWORD trong .env cuc bo de tao tai khoan.")
    ensure_prototype_owner_auth(data_dir, password)
    print("Dang nhap ban thu: Tou hoac Chibun. Mat khau dung theo cau hinh da chot.", flush=True)
    return data_dir


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description="Chay AI Company Lite tren may ca nhan")
    parser.add_argument("--check", action="store_true", help="Kiem tra Python/thu vien ma khong mo web")
    parser.add_argument("--no-browser", action="store_true", help="Khong tu mo trinh duyet")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.error("Can Python 3.12 tro len. Hay dung Python da cai du an.")
    if not 1 <= args.port <= 65535:
        parser.error("Port phai nam trong khoang 1-65535.")
    if os.environ.get("AI_COMPANY_PROFILE", "lite").lower() != "lite":
        parser.error("Nut khoi dong nay chi danh cho profile Lite cuc bo.")
    print(f"Python dang dung: {sys.executable}", flush=True)
    ensure_dependencies()
    if args.check:
        print("Thu vien Lite da san sang. Khong can API key de chay mock.", flush=True)
        return 0

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
    data_dir = ensure_owner_access(environment)
    environment["AI_COMPANY_DATA_DIR"] = str(data_dir)

    url = f"http://127.0.0.1:{args.port}"
    if healthy(url):
        if not login_available(url):
            print("Web cu chua co dang nhap dang chiem port. Hay dung web cu roi mo lai launcher.", file=sys.stderr)
            return 1
        print(f"Web da chay tai {url}; khong mo them ban thu hai.", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    api: subprocess.Popen | None = None
    worker: subprocess.Popen | None = None
    try:
        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ai_company.api.main:create_app", "--factory",
             "--host", "127.0.0.1", "--port", str(args.port), "--no-access-log"],
            cwd=ROOT, env=environment,
        )
        deadline = time.monotonic() + 25
        while not healthy(url):
            if api.poll() is not None:
                print("API khong khoi dong duoc; xem loi phia tren.", file=sys.stderr)
                return 1
            if time.monotonic() >= deadline:
                print("API chua san sang sau 25 giay; xem loi phia tren.", file=sys.stderr)
                return 1
            time.sleep(0.25)
        worker = subprocess.Popen(
            [sys.executable, "-m", "ai_company.worker.mock_cli", "--loop"],
            cwd=ROOT, env=environment,
        )
        print(f"Web da san sang: {url}", flush=True)
        print("Giu cua so nay mo khi dung web. Nhan Ctrl+C de dung web va worker.", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        while True:
            if api.poll() is not None or worker.poll() is not None:
                print("API hoac worker da dung; xem thong bao phia tren.", file=sys.stderr)
                return 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Dang dung AI Company Lite...", flush=True)
        return 0
    finally:
        stop(worker)
        stop(api)


if __name__ == "__main__":
    raise SystemExit(main())

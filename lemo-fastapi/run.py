import argparse
import os
import subprocess
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the LEMO FastAPI server.")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn auto-reload")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", default="8000", help="Bind port")
    return parser.parse_args()


def _reload_enabled(args: argparse.Namespace) -> bool:
    if args.no_reload:
        return False
    if args.reload:
        return True
    return os.getenv("UVICORN_RELOAD", "true").lower() in ("1", "true", "yes")


def _print_runtime_hint() -> None:
    root = Path(__file__).resolve().parent
    local_venv = root / "venv" / "Scripts" / "python.exe"
    print(f"[run.py] using python: {sys.executable}")
    if local_venv.exists() and Path(sys.executable).resolve() != local_venv.resolve():
        print(f"[run.py] repo venv detected at: {local_venv}")
        print("[run.py] active interpreter differs from repo venv; package mismatches can cause runtime errors.")


if __name__ == "__main__":
    try:
        args = _parse_args()
        reload_enabled = _reload_enabled(args)
        env = os.environ.copy()
        env["UVICORN_RELOAD"] = "true" if reload_enabled else "false"

        _print_runtime_hint()

        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            str(args.host),
            "--port",
            str(args.port),
        ]
        if reload_enabled:
            command.append("--reload")

        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Error running uvicorn: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)

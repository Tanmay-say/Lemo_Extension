import subprocess
import sys
import os

if __name__ == "__main__":
    try:
        reload_enabled = os.getenv("UVICORN_RELOAD", "true").lower() in ("1", "true", "yes")
        env = os.environ.copy()
        env["UVICORN_RELOAD"] = "true" if reload_enabled else "false"

        command = [
            sys.executable, "-m", "uvicorn", 
            "main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
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

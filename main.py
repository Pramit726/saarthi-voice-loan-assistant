from __future__ import annotations

import os
import subprocess
import sys

import uvicorn

SOURCE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SOURCE_ROOT not in sys.path:
    sys.path.insert(0, SOURCE_ROOT)

from saarthi.config import get_settings


def main() -> None:
    settings = get_settings()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = SOURCE_ROOT + os.pathsep + environment.get("PYTHONPATH", "")
    worker = subprocess.Popen(
        [sys.executable, "-m", "saarthi.agent.worker", "dev"],
        env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        uvicorn.run("saarthi.main:app", host=settings.api_host, port=settings.api_port)
    finally:
        worker.terminate()
        worker.wait(timeout=10)


if __name__ == "__main__":
    main()

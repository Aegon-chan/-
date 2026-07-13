\"\"\"Python sidecar launcher for Tauri desktop wrapper.

Starts the backend (FastAPI) and frontend (NiceGUI) servers,
shutting them down cleanly when the sidecar process is terminated.
\"\"\"
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("research_agent.sidecar")
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
PYTHON = sys.executable


def _find_free_port(start: int = 8010) -> int:
    import socket
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    os.chdir(BACKEND_DIR.parent)  # project root

    backend_port = _find_free_port(8010)
    frontend_port = _find_free_port(8080)

    processes: list[subprocess.Popen] = []

    # Start backend
    env = dict(os.environ)
    env["APP_ENV"] = "production"
    env["APP_DEBUG"] = "false"
    backend = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "backend.main:app",
         "--host", "127.0.0.1", "--port", str(backend_port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(backend)

    # Start frontend (NiceGUI)
    frontend = subprocess.Popen(
        [PYTHON, "-m", "frontend.app",
         "--host", "127.0.0.1", "--port", str(frontend_port),
         "--backend-url", f"http://127.0.0.1:{backend_port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(frontend)

    logger.info(
        "Sidecar started: backend=:%d frontend=:%d",
        backend_port, frontend_port,
    )

    # Print URLs for the Tauri webview to pick up
    print(f"BACKEND_URL=http://127.0.0.1:{backend_port}", flush=True)
    print(f"FRONTEND_URL=http://127.0.0.1:{frontend_port}", flush=True)

    def shutdown(*_):
        logger.info("Shutting down servers...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        while True:
            time.sleep(1)
            # Check if any child died
            for i, p in enumerate(processes):
                if p.poll() is not None:
                    logger.error("Process %d exited with code %d", i, p.returncode)
                    shutdown()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()

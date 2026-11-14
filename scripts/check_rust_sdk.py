"""Host a local backend and exercise the generated Rust client against it."""

from __future__ import annotations

import os
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
COMMAND = [
    "cargo",
    "run",
    "--locked",
    "--manifest-path",
    str(ROOT / "sdk/rust/Cargo.toml"),
    "-p",
    "server-browser-client",
    "--example",
    "browser-smoke",
    "--",
]


def main() -> None:
    # Build before reserving the listener; run the example only after startup.
    subprocess.run(
        [
            "cargo",
            "build",
            "--locked",
            "--manifest-path",
            str(ROOT / "sdk/rust/Cargo.toml"),
            "--examples",
        ],
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="rust-sdk-interop-") as temporary:
        environment = {
            **os.environ,
            "CONFIG_DIR": temporary,
            "ADMIN_KEY": "local-test-admin",
            "TRUSTED_PROXY_CIDRS": "",
        }
        environment.pop("DISCORD_SIGNING_KEYRING", None)
        with (
            patch.dict(os.environ, environment, clear=True),
            socket.socket() as listener,
        ):
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            base_url = f"http://127.0.0.1:{listener.getsockname()[1]}"
            server = uvicorn.Server(
                uvicorn.Config(
                    "server_browser_backend.main:app",
                    proxy_headers=False,
                    access_log=False,
                    log_level="warning",
                )
            )
            worker = threading.Thread(
                target=server.run, kwargs={"sockets": [listener]}, daemon=True
            )
            worker.start()
            try:
                deadline = time.monotonic() + 10
                while not server.started:
                    if not worker.is_alive():
                        raise RuntimeError("Local backend exited during startup")
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Local backend startup timed out")
                    time.sleep(0.05)
                subprocess.run(COMMAND + [base_url], cwd=ROOT, check=True)
            finally:
                server.should_exit = True
                worker.join(timeout=10)
                if worker.is_alive():
                    raise RuntimeError("Local backend failed to stop")


if __name__ == "__main__":
    main()

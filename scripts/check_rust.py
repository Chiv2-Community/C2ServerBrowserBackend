"""Run the shared Rust validation sequence on Linux and Windows."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "sdk/rust/Cargo.toml"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", action="store_true", help="also verify crate archives")
    args = parser.parse_args(argv)
    checks = [
        ["fmt", "--all", "--", "--check"],
        ["clippy", "--locked", "--workspace", "--all-targets", "--all-features"],
        ["clippy", "--locked", "--workspace", "--all-targets", "--no-default-features",
         "--features", "server-browser-client/rustls-tls,server-browser-client-sdk/rustls-tls"],
        ["doc", "--locked", "--workspace", "--all-features", "--no-deps"],
        ["test", "--locked", "--workspace"],
        ["test", "--locked", "--workspace", "--release", "--all-features"],
    ]
    for command, *options in checks:
        subprocess.run(
            ["cargo", command, "--manifest-path", MANIFEST, *options],
            cwd=ROOT,
            check=True,
        )
    if args.package:
        # Cargo caches workspace-registry crates by target path and version.
        # A fresh path prevents reuse of older same-version workspace packages.
        with tempfile.TemporaryDirectory(prefix="server-browser-crates-") as temporary:
            subprocess.run(
                ["cargo", "package", "--manifest-path", MANIFEST, "--locked",
                 "--workspace", "--allow-dirty", "--target-dir", temporary],
                cwd=ROOT,
                check=True,
            )
            destination = ROOT / "sdk/rust/target/package"
            destination.mkdir(parents=True, exist_ok=True)
            for archive in (Path(temporary) / "package").glob("*.crate"):
                shutil.copyfile(archive, destination / archive.name)


if __name__ == "__main__":
    main()

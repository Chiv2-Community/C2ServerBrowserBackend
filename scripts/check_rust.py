"""Run the shared Rust validation sequence on Linux and Windows."""

from __future__ import annotations

import argparse
import subprocess
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
    if args.package:
        checks.append(["package", "--locked", "--workspace", "--allow-dirty"])
    for command, *options in checks:
        subprocess.run(
            ["cargo", command, "--manifest-path", MANIFEST, *options],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    main()

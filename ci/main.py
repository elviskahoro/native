# ruff: noqa: INP001, T201
"""Native CI checks as a plain Dagger SDK program (no Dagger module).

Run through `ci/run.sh <subcommand>`, which wraps `dagger run python ci/main.py`.
Subcommands: pyright, pyrefly, all.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import dagger
from dagger import dag

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pins. Keep in sync with .trunk/trunk.yaml where the tool is also a Trunk linter.
PYTHON_IMAGE = "python:3.11.13-slim-bookworm"
UV_VERSION = "0.11.29"
PYRIGHT_VERSION = "1.1.414"
PYREFLY_VERSION = "1.3.1"

SRC = "/src"
VENV = "/opt/venv"
UV_CACHE = "/root/.cache/uv"

# Only what the checkers read. Never upload .git, venvs, build output, or .context.
SOURCE_EXCLUDES = [
    ".git",
    ".venv",
    ".context",
    ".web",
    ".states",
    "**/__pycache__",
    "node_modules",
    "dist",
    "build",
    "assets/external",
]


def base() -> dagger.Container:
    """Toolchain + locked dev deps. Source-independent, so it caches across source edits."""
    uv_cache = dag.cache_volume("native-ci-uv")
    manifests = dag.host().directory(
        str(REPO_ROOT),
        include=["pyproject.toml", "uv.lock", ".python-version"],
    )
    return (
        dag.container()
        .from_(PYTHON_IMAGE)
        .with_env_variable("UV_LINK_MODE", "copy")
        .with_env_variable("UV_PROJECT_ENVIRONMENT", VENV)
        .with_env_variable("UV_TOOL_DIR", "/opt/uv-tools")
        .with_env_variable("UV_TOOL_BIN_DIR", "/usr/local/bin")
        .with_env_variable("PATH", f"{VENV}/bin:/usr/local/bin:/usr/bin:/bin")
        .with_mounted_cache(UV_CACHE, uv_cache)
        # pyright's bundled node needs libatomic.
        .with_exec(
            [
                "sh",
                "-c",
                "apt-get update -qq && apt-get install -y -qq --no-install-recommends libatomic1 && rm -rf /var/lib/apt/lists/*",
            ],
        )
        .with_exec(["pip", "install", "--no-cache-dir", f"uv=={UV_VERSION}"])
        .with_exec(["uv", "tool", "install", f"pyright=={PYRIGHT_VERSION}"])
        .with_exec(["uv", "tool", "install", f"pyrefly=={PYREFLY_VERSION}"])
        .with_workdir(SRC)
        .with_directory(SRC, manifests)
        .with_exec(
            ["uv", "sync", "--frozen", "--no-install-project", "--group", "dev"],
        )
        # Warm pyright's node runtime so it is cached with this layer.
        .with_exec(["pyright", "--version"])
    )


def with_source(ctr: dagger.Container) -> dagger.Container:
    source = dag.host().directory(str(REPO_ROOT), exclude=SOURCE_EXCLUDES)
    return ctr.with_directory(SRC, source)


async def run_check(name: str, args: list[str], paths: list[str]) -> None:
    await with_source(base()).with_exec([*args, *paths]).sync()
    sys.stderr.write(f"{name}: ok" + "\n")


def pyright_args() -> list[str]:
    return [
        "pyright",
        "--pythonpath",
        f"{VENV}/bin/python",
        "--project",
        "pyrightconfig.json",
    ]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=["pyright", "pyrefly", "all"])
    parser.add_argument(
        "paths",
        nargs="*",
        help="limit to these paths (default: whole project)",
    )
    ns = parser.parse_args()

    checks = {
        "pyright": pyright_args(),
        "pyrefly": [
            "pyrefly",
            "check",
            "--python-interpreter-path",
            f"{VENV}/bin/python",
        ],
    }
    selected = list(checks) if ns.check == "all" else [ns.check]
    try:
        async with dagger.connection(dagger.Config(log_output=sys.stderr)):
            results = await asyncio.gather(
                *(run_check(n, checks[n], ns.paths) for n in selected),
                return_exceptions=True,
            )
    except dagger.DaggerError as exc:
        sys.stderr.write(f"dagger error: {exc}" + "\n")
        return 1
    failed = [
        (n, r)
        for n, r in zip(selected, results, strict=True)
        if isinstance(r, BaseException)
    ]
    for n, r in failed:
        sys.stderr.write(f"{n}: FAILED\n{r}" + "\n")
        if isinstance(r, dagger.ExecError):
            print(
                f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}",
                file=sys.stderr,
            )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

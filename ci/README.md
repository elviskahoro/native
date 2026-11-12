# CI checks (Dagger)

`ci/main.py` is a plain Dagger SDK program (no Dagger module, no `dagger.json`)
that runs the pyright and pyrefly checks in a pinned container. RWX
(`.rwx/ci.yml`) and local runs call the same code.

## Run locally

Needs Docker, `uv`, and the `dagger` CLI **0.21.8** (matches `dagger-io==0.21.8`).

```bash
ci/run.sh all                      # pyright + pyrefly in parallel
ci/run.sh pyright native/foo.py    # one check, optional paths
```

`ci/run.sh` is `dagger run uv run --project ci python ci/main.py "$@"`. On
Dagger 1.x the entry point becomes `dagger api with-session`; update
`ci/run.sh` and `.rwx/ci.yml` together if you re-pin.

## Run on RWX

```bash
rwx run .rwx/ci.yml --wait
rwx run .rwx/ci.yml --wait --init paths="native/foo.py"
```

Dagger does not run in Conductor cloud sandboxes (no Docker); use RWX there.

## Layers

| Layer | Where | What |
| --- | --- | --- |
| A | RWX tasks `uv-install`, `dagger-cli-install` (sha256-pinned), `dagger-engine-warm`, `ci-deps` | none read the checkout beyond `ci-deps`' filter, so they cache across commits |
| B | RWX `code` | git clone |
| C | `checks` task -> `ci/run.sh all` | pyright 1.1.414 and pyrefly 1.3.1 in `python:3.11.13-slim-bookworm`, uv 0.11.29, locked `--group dev` deps |

Inside Dagger the toolchain and dependency layers are built from
`pyproject.toml`, `uv.lock`, `.python-version` only, so a source edit
re-runs just the check commands. The uv cache is a Dagger cache volume.

Expected cache behavior on RWX: docs-only or source-only change re-runs only
`checks` (`cache: false`); a `ci/` lockfile change re-runs `ci-deps`; a root
`uv.lock` change rebuilds the Dagger dependency layer inside `checks`.

## Not adopted

RWX `tool-cache`/vault persistence of Dagger state is not set up: the
pipeline is manual-only and a cold run takes about 40 seconds. Revisit if
that grows.

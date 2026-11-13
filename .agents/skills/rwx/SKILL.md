---
name: rwx
description: Authenticate and use the RWX CLI. Run RWX CI on the working tree (including uncommitted changes), type-check with pyright/pyrefly without a local venv, read run results and logs, and create, lint, or modify `.rwx/*.yml`. Use when asked about RWX, when "CI failed" or "CI is red", or when asked to run tests or fetch logs on RWX.
---

# RWX CLI in this repo

CI definitions live in `.rwx/`. Merge gates run in GitHub Actions and the Trunk
Merge Queue (see `AGENTS.md`). The RWX pipelines are manual only, with no PR or
push trigger, so they are not required statuses.

| File | Purpose |
| --- | --- |
| `.rwx/ci.yml` | pyright + pyrefly, run through the Dagger program in `ci/` |

## Auth: injected tokens, one per RWX workspace

Env vars named `RWX_ACCESS_TOKEN_<SUFFIX>` or `RWC_ACCESS_TOKEN_<SUFFIX>` are
injected. Each token is scoped to one RWX workspace; `<SUFFIX>` is the
workspace name, uppercased. List the names without values:

```bash
env | grep -E '^RW[XC]_ACCESS_TOKEN_' | cut -d= -f1
```

The CLI reads only `RWX_ACCESS_TOKEN` (or `--access-token`). Export the token
whose suffix matches the repo owner (from the `origin` URL, uppercased). Never
print it:

```bash
OWNER=$(git remote get-url origin | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#' | tr a-z A-Z)
export RWX_ACCESS_TOKEN="$(printenv "RWX_ACCESS_TOKEN_$OWNER" || printenv "RWC_ACCESS_TOKEN_$OWNER")"
rwx whoami   # confirms organization and user, does not show the token
```

The shell does not persist between tool calls, so export per command. A run,
task, or log ID only resolves under the workspace that owns it. On
not-found or unauthorized, try the other token. Without any token,
`rwx login` authorizes interactively.

## Running a pipeline with your current git changes

`rwx run` sends a git patch with the run, so no commit or push is needed:

- Base: the closest ancestor of local `HEAD` that is already on `origin`
  (`event.git.sha` resolves to it).
- Patch on top: unpushed commits, staged, unstaged, and untracked files.
- Excluded: anything in `.gitignore`. Git LFS changes error out.
- `RWX_DISABLE_GIT_PATCH=1` turns patching off.

```bash
rwx run .rwx/ci.yml --wait                    # run, block, print results
rwx run .rwx/ci.yml --wait --fail-fast        # stop at first failure
rwx run .rwx/ci.yml --target <task-key> --wait  # one task plus its deps
rwx run .rwx/ci.yml --title "wip: my change" --json
rwx run .rwx/ci.yml --wait --init paths="app/foo.py app/bar.py"
```

Keep the `git/clone` task's `ref: ${{ init.commit-sha }}` and the `cli`
trigger's `commit-sha: ${{ event.git.sha }}` when editing `.rwx/*.yml`. That
wiring is what makes the patch apply.

## Type checking without a local `.venv`

Use `ci.yml` when there is no `.venv` or memory is tight.
Both accept `paths` (space separated; empty means the whole project).

```bash
rwx run .rwx/ci.yml --wait
rwx run .rwx/ci.yml --wait --init paths="app/foo.py"
```

## Results and logs ("CI failed")

```bash
rwx runs list
rwx results <run-id>                        # status and failures; `rwx results -h` for branch/commit lookup
rwx logs <task-id>                          # a failed run prints the failing task id
rwx logs <run-id> --task <task-key> --output /tmp/logs
rwx artifacts --help                        # download task artifacts
rwx retry <run-id>                          # retry a run or task
rwx cancel <run-id>
```

Use `--json` where available for parsing.

## Sandboxes and debugging

```bash
rwx sandbox exec -- <command>   # run in a persistent RWX sandbox
rwx debug <task-id>             # debug a task; `rwx ssh` attaches to a running one
```

## Writing or changing `.rwx/*.yml`

1. Pull the reference docs and read them in full, untruncated:
   `rwx docs pull /migrating/rwx-reference`.
2. For anything else: `rwx docs search "<query>"`, then `rwx docs pull <path>`
   (for example `/docs/cli-triggers`, `/docs/cli-reference/rwx-run`). Use
   these instead of WebFetch.
3. Validate after every edit: `rwx lint .rwx/<name>.yml`.
4. Prefer packaged leaves over hand-rolled steps; `rwx lint` flags outdated
   versions, and `rwx update` / `rwx resolve` bump or pin base images and
   packages.
5. Model tasks as a DAG: separate install from checks, and `filter:` install
   tasks to lockfile inputs (see `ci.yml`) so caching survives ordinary
   commits. RWX caches by content, so drop GitHub-style cache steps.
6. If you must download an installer, pin the version and verify its checksum,
   as `ci.yml` does for uv.

## Migrating a GitHub Actions workflow

Upstream skills: https://github.com/rwx-cloud/skills (`migrate-from-gha`,
`review-gha-migration`). The approach: inventory jobs, `needs:`, secrets and
env first, translate to a DAG using RWX packages, run `rwx lint`, then review
the result against the inventory for dropped steps. Do not migrate the
workflows that gate the merge queue without a request to do so.

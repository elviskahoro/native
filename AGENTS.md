# Buridan Native Framework - Agent Guide

## Overview

Native is a framework for building native applications using Python.

This repository contains the framework source code, UI components,
documentation, examples, and supporting tooling.

When working with Native, prefer the repository documentation and existing
patterns over assumptions or general framework knowledge.

## Documentation

The primary documentation lives in:

```text
docs/
```

The public documentation site is:

https://native.buridan.dev/

### Documentation URL Mapping

Repository documentation paths map to public URLs.

Example:

```text
docs/getting_started/introduction.md
```

maps to:

```text
https://native.buridan.dev/docs/getting-started/introduction
```

Rules:

- Underscores in paths become hyphens in URLs.
- Markdown extensions are removed.
- The `/docs/` prefix is preserved.

### Component Documentation

Component documentation lives in:

```text
docs/components/
```

Component URLs follow:

```text
https://native.buridan.dev/components/<component-name>
```

Example:

```text
docs/components/button.md
```

maps to:

```text
https://native.buridan.dev/components/button
```

## Development Principles

When modifying Native:

- Prefer existing components and patterns before creating new ones.
- Follow existing naming conventions.
- Keep APIs consistent with existing components.
- Update documentation when adding user-facing features.
- Match existing architecture and design decisions.
- Avoid introducing unnecessary abstractions.
- Look for similar existing implementations before creating new ones.

## Documentation Priority

When information conflicts, use this priority:

1. Repository documentation
2. Source code implementation
3. Existing project patterns
4. General framework knowledge

The Native documentation and source code are the source of truth.

## Landing PRs

PRs land through the Trunk Merge Queue, not the GitHub Merge button.

- Submit: `trunk merge <pr-number>` (a number, not a URL or branch name).
- Check once: `trunk merge status <pr-number>`. States: Queued, Testing,
  Tests Passed, Merged. Report the state and stop. Never poll in a loop.
- Never use `gh pr merge` or the GitHub Merge button. They bypass the queue.
- Never use `--force`, `pause` or `resume`.
- Leave priority at the default (`medium`). `urgent` and `high` are for
  incidents and need an explicit reason from the user.
- Failed or PENDING_FAILURE: PENDING_FAILURE may be a flake, so retry once.
  Failed means push a fix to the PR branch and resubmit. Do not resubmit
  blindly in a loop.
- Auth failure: run `trunk login` once and retry.
- Refuse to queue from main or a protected branch.
- A `Closes #N` line in the PR body auto-closes the issue when the queue lands
  the PR. Do not close the issue by hand beforehand.

The queue gates on the statuses in `.trunk/trunk.yaml` →
`merge.required_statuses` ("Trunk Check", "Unit tests", "Generate & Verify
Docs and Social Cards", "pullfrog-approval"). The three workflow gates
trigger on every PR to `main` and on the queue's `trunk-merge/**` test
branches; `pullfrog-approval` is posted by the Pullfrog App on PRs it
reviews (the queue's Draft-PR test branches included), so merges wait for
Pullfrog's approval verdict. The GitHub "main - PRs" ruleset requires the
same checks plus "Entire Gates"; the queue deliberately does not wait on
"Entire Gates" because the Entire App may not post it on the queue's
`trunk-merge/**` test branches, which would stall them. Keep the rest of
the two lists in sync (the ruleset pins `pullfrog-approval` to the Pullfrog
App's integration ID). The queue
itself is created in the Trunk web app (app.trunk.io); do not attempt to
configure it from the repo.

If a queued PR stalls in Testing because `pullfrog-approval` never
reports, run `trunk merge cancel <pr-number>`, request a review with an
`@pullfrog` comment on the PR, then resubmit. During a Pullfrog outage a
repo admin can temporarily drop the check from the ruleset and
`merge.required_statuses` (the ruleset has no bypass actors) and restore
both afterwards.

If a PR is blocked from merging on "Entire Gates" (enforced by the ruleset,
not the queue), open the trail linked from the check, resolve or fix the
listed findings or approvals, and push; the gate recomputes on the new
head. `trunk merge cancel <pr-number>` first if it was already queued.

## Agent Skills

Specialized agent skills are located at:

```text
.agents/skills/
```

Use the most specific skill available for the task.

Available skills:

### getting-started

Covers:

- Installing Native
- Creating a project
- CLI usage
- Development workflow
- Basic configuration

Location:

```text
.agents/skills/getting-started/SKILL.md
```

### components

Covers:

- Native UI components
- Component APIs
- Creating new components
- Component usage patterns

Location:

```text
.agents/skills/components/SKILL.md
```

### theming

Covers:

- Styling
- Themes
- Colors
- Visual customization

Location:

```text
.agents/skills/theming/SKILL.md
```

## Working With Native

Before implementing a feature:

1. Check whether an existing component or pattern already exists.
2. Read the relevant documentation.
3. Follow existing APIs and conventions.
4. Update documentation if the feature is user-facing.
5. Keep changes focused and consistent with the project.

## When Adding New Features

For new components:

- Follow existing component structure.
- Add documentation.
- Add examples when appropriate.
- Ensure the component fits existing design patterns.

For framework changes:

- Understand the existing architecture first.
- Avoid breaking public APIs unless necessary.
- Document important decisions.

## General Guidance

When answering questions about Native:

- Prefer Native-specific examples.
- Use the documented API style.
- Avoid suggesting unsupported patterns.
- Point users toward the relevant documentation.
- Load specialized skills when available.

<!-- entire-agent:begin -->
Read .entire/agent-guide.md for this repository's workflow, source inspection, and verification guidance.
@.entire/agent-guide.md
<!-- entire-agent:end -->

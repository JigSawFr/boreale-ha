<!--
The title must be a conventional commit with a scope (feat(config-flow): …, fix(statistics): …,
docs(readme): …): CI checks it, and the squash merge makes it the commit subject that
release-please writes the changelog from.
-->

## What this changes, and why

<!-- The diff says what; this says what it is for. Link the issue it closes, if any. -->

## How it was verified

<!-- Beyond CI. Say whether it ran in a real Home Assistant (version), with a real console (PlayGuard version) or only in the tests. -->

## Checklist

- [ ] `ruff check`, `ruff format --check` and `pytest` pass; `scripts/coverage_per_module.py` keeps every module above 95%
- [ ] `quality_scale.yaml` is still true (no rule left behind)
- [ ] New strings are in `translations/en.json` and `translations/fr.json`; icons in `icons.json`
- [ ] An entity change follows PlayGuard's `entities.json` (or the console's change comes first)
- [ ] A change users can see is in both README.md and README.fr.md

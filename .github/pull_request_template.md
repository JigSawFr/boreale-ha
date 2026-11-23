<!--
Title: a Conventional Commit with a scope (feat(config-flow): …, fix(statistics): …,
docs(readme): …). CI checks it, and the squash merge makes it the changelog entry.
-->

## ✨ At a glance

<!-- One or two sentences: what this does, for whom. -->

## 🎯 Why

<!-- The problem or the need. Link the issue it closes, if any. -->

## 🔧 What changes

<!-- What the diff does not say: visible behaviour, entities, migrations. -->

## ✅ Checked

<!-- What CI does not cover: a real Home Assistant (version), a real console
(PlayGuard version), or only the tests. Say so when no code changed. -->

Only what CI does not check (ruff, pytest, coverage, hassfest, hacs and the title are in CI):

- [ ] `quality_scale.yaml` is still true (no rule left behind)
- [ ] New strings are in `translations/en.json` and the 13 other languages; icons in `icons.json`
- [ ] An entity change follows PlayGuard's `entities.json` (or the console's change comes first)
- [ ] A user-visible change is in both `README.md` and `README.fr.md`

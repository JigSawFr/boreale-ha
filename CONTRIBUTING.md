# Contributing to PlayGuard for Home Assistant

## No code needed

A bug report with the console's diagnostics, a feature request, a fix in the French or
English text: all welcome. [Getting help](.github/SUPPORT.md) says where each one goes,
and what belongs to [PlayGuard](https://github.com/JigSawFr/PlayGuard) itself (what the
console does with an order, its *Remote access* settings, its own Home Assistant device).

## Set-up

Python 3.14, as Home Assistant 2026.10:

```sh
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt    # Home Assistant 2026.10.1 and its test harness
pip install ruff==0.17.0
```

To try it in a real Home Assistant, copy (or link) `custom_components/boreale` into the
`custom_components` folder of a test configuration, with an MQTT broker and a console
running PlayGuard with *Remote access* on, or retained documents from
[`tests/fixtures/`](tests/fixtures/) published on the broker by hand.

## Tests and CI

```sh
ruff check custom_components tests scripts
ruff format --check custom_components tests scripts
python -m pytest --cov=custom_components.boreale --cov-branch --cov-report=term --cov-report=json
python scripts/coverage_per_module.py coverage.json   # more than 95% of every module
python scripts/package.py                             # dist/boreale.zip, as a release builds it
```

`validate.yml` runs the same on every pull request, plus Home Assistant's hassfest and
HACS's checks, and `codeql.yml` the static analysis. A new code path comes with its test:
the coverage gate is per module, not the total.

- **The quality scale.** [`quality_scale.yaml`](custom_components/boreale/quality_scale.yaml)
  says where the integration stands on Home Assistant's
  [Integration Quality Scale](https://contributors.home-assistant.io/core/quality-scale/rules/)
  (Platinum): each rule *done*, or *exempt* with the reason. hassfest skips that file for a
  custom integration, so `tests/test_quality_scale.py` checks it. A change that breaks a
  rule (an untranslated error, an entity without a category it needs, a module under 95%)
  is fixed, not marked *todo*.
- **The entities follow PlayGuard's table.** `custom_components/boreale/entities.py`,
  with the names in `translations/` and the icons in `icons.json`, mirrors PlayGuard's
  entity table (`source/sync/sync_entities.c`). PlayGuard's host tests export it as
  `build/host-tests/sync/entities.json` (`make test`); copy that file to
  `tests/fixtures/entities.json` when it changes: `tests/test_parity.py` fails until the
  integration follows. `tests/fixtures/state.json` and `activity.json` are PlayGuard's own
  examples, from the same folder. A change the console must make first goes to PlayGuard
  (label `playguard` here).
- **Translations.** `translations/en.json` is the source (there is no `strings.json`), and
  `translations/fr.json` follows it in the same pull request: entity names, options,
  errors, repairs, actions. The other languages (those of PlayGuard's catalogs that Home
  Assistant has: de, es, es-419, it, ja, ko, nl, pt, pt-BR, ru, zh-Hans, zh-Hant) follow
  too, their console labels as PlayGuard's catalogs word them; `tests/test_translations.py`
  checks that each has every key, no other, and the same placeholders.
- **Icons** live in `icons.json`, never in the Python.

## Code layout

| Path | Content |
|---|---|
| `custom_components/boreale/__init__.py` | Set-up and unload of a console's entry, the actions registered once |
| `coordinator.py` | The console's push coordinator: MQTT subscriptions, its documents, orders, the take-over of the console's own discovery, repair issues |
| `entities.py`, `const.py` | The entity table, mirrored from PlayGuard's; the topics, schema and option names |
| `entity.py` and one module per platform | The entities (`binary_sensor`, `button`, `calendar`, `event`, `image`, `lock`, `number`, `select`, `sensor`, `switch`, `time`, `update`) |
| `play.py` | Today's and the week's play time, per game and per account, as the sensors, `get_play_time` and Assist read them |
| `trigger.py`, `condition.py`, `automation.py`, `triggers.yaml`, `conditions.yaml` | The console's own triggers and conditions in the automation editor |
| `intent.py`, `llm.py` | The intents for Assist, and the same as tools of Home Assistant's LLM API |
| `logbook.py` | The console's events (`playguard_event`) in the logbook |
| `config_flow.py` | MQTT discovery, adding by hand, options, reconfigure |
| `services.py`, `services.yaml` | The actions (`get_play_time` with a response) |
| `statistics.py` | Finished days into the recorder's long-term statistics |
| `repairs.py`, `diagnostics.py` | The fixable repair, the redacted diagnostics |
| `brand/` | The integration's icon and logos (Home Assistant 2026.3+), rendered from `branding/` by `scripts/render_branding.mjs` |
| `blueprints/automation/boreale/` | The blueprints the README offers to import (`tests/test_blueprints.py` sets each one up) |
| `tests/` | One test module per part, PlayGuard's fixtures, the parity, translation and quality-scale checks |
| `scripts/` | The per-module coverage gate, the release zip, the pre-release's version (`prerelease.py`), the README's branding |
| `branding/` | The icon (a house around Aurore's night and PlayGuard's play sign), the logos, the README's banner and the social preview, as SVG, in Aurore's aurora (its sky, its colours, Sora): `node scripts/render_branding.mjs` (Node and Playwright) renders them to `brand/` and `.github/readme/` |
| `.github/readme/` | The README's images: the banner, the social preview (uploaded by hand in *Settings › General*), the screenshots (a demo console in a real Home Assistant) |

## Formats

What crosses a version boundary carries a version. A document of a newer `schema` is not
read (the last one known stays, a repair says so), one without `schema` is schema 1, and
a field the integration does not know is skipped; `tests/test_init.py`,
`test_published.py` and `test_statistics.py` cover each case.

| Format | Version | Writer → reader |
|---|---|---|
| MQTT `state`, `system`, `games`, `activity`, `activity/<date>`, `names`, `week`, `event` | `schema`, `SCHEMA` 1 in `const.py` | PlayGuard → `coordinator.py` (`_readable`), then the entities and `statistics.py` |
| MQTT `integration` | `schema`, `SCHEMA` 1 | `coordinator.py` → PlayGuard |
| The config entry | `VERSION` 1, `MINOR_VERSION` 3 (`config_flow.py`) | migrated by `async_migrate_entry` (`__init__.py`) |

## Pull requests and releases

Releases are automated with [release-please](https://github.com/googleapis/release-please),
which reads [conventional commits](https://www.conventionalcommits.org/), as PlayGuard's:

- Give each pull request a conventional title with a scope, the part of the integration it
  changes (`feat(config-flow): …`, `fix(statistics): …`, `docs(readme): …`,
  `feat(entities)!: …` for a breaking change); CI checks it (`pr-title.yml`).
  release-please sorts each section of the changelog by scope, so a title without one
  lands apart from the rest. Scopes in use: `integration`, `config-flow`, `coordinator`,
  `entities`, `sensors`, `events`, `accounts`, `week`, `availability`, `device`,
  `calendar`, `blueprints`, `native`, `services`, `statistics`, `repairs`,
  `diagnostics`, `translations`, `brand`, `readme`, `release`, `repo`, `deps`.
- **Squash-merge** pull requests, so each one lands as a single commit carrying that title.
- release-please keeps a `chore(main): release X.Y.Z` PR open
  ([`CHANGELOG.md`](CHANGELOG.md), `version` in `manifest.json`); merging it tags
  `vX.Y.Z` and publishes the release. `release-please.yml` then attaches **`boreale.zip`**
  (what HACS installs, `hacs.json`'s `zip_release`), `SHA256SUMS.txt` and a
  [build provenance attestation](https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations):
  `gh attestation verify boreale.zip -R JigSawFr/boreale-ha` checks that a download was
  built by this repository's CI. `scripts/package.py` gives the zip fixed dates (the tag's
  commit), order and modes, so the same tag gives the same bytes, and refuses a tag that is
  not `manifest.json`'s version.
- **Pre-releases**: each update of the release PR is also published, by `release-please.yml`'s
  `prerelease` job, as a GitHub pre-release `vX.Y.Z-dev.N` of the PR's head: the next
  version, `manifest.json` stamped with it (`scripts/prerelease.py stamp`), the PR's
  changelog section as its notes, the same zip, checksum and attestation. HACS offers it to
  whoever turns the repository's *Pre-release* switch on. A head already published is not
  published again; the 5 newest of a version are kept, and all of them are deleted once
  `vX.Y.Z` is released. Nothing to merge for a pre-release: merging the release PR stays the
  only way to a release.
- release-please runs with a token of the *PlayGuard Release* GitHub App when the
  repository has it (variable `RELEASE_APP_CLIENT_ID`, secret `RELEASE_APP_PRIVATE_KEY`;
  permissions Contents, Pull requests and Issues: write): its pushes to the release PR run
  the checks. Without it, `GITHUB_TOKEN`: releases still work, the release PR just gets no
  CI run.
- Dependabot moves the pinned actions and the test harness (`requirements_test.txt`, one
  per Home Assistant release) with `ci(deps)` titles. The minimum Home Assistant
  (`hacs.json`, the README) moves by hand, when the integration needs it.

When a change is visible to users, update [README.md](README.md) and
[README.fr.md](README.fr.md) **both**.

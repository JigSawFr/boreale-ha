# PlayGuard for Home Assistant

A Home Assistant integration for [PlayGuard](https://github.com/JigSawFr/PlayGuard),
the Nintendo Switch homebrew that manages parental controls offline. PlayGuard
publishes the console's state, play time and events on an MQTT broker and
takes orders from it (*Preferences › Remote access*, and its optional agent
that keeps the link up while PlayGuard is closed). This integration turns
that into a proper Home Assistant device.

The console works with Home Assistant **without** this integration: it
publishes Home Assistant's MQTT discovery itself. The integration adds:

- **Found by itself**: every console that publishes on the broker is offered
  for set-up, no id to type.
- **The same entities** as the console's own MQTT device (names, units,
  options), replacing it (no duplicates; turn it back on in the options),
  plus **Online**, **Agent running** and **Play time this week**. Home
  Assistant builds the entity ids itself, from the device's and the
  entities' names, when they are first registered, and you can change them:
  check the automations that use the console's former entities.
- **Game names** on *Now playing*, and each game's time today and this week as
  attributes.
- **Long-term statistics**: every finished day's total, and each game's,
  imported into the recorder (`playguard:<console id>_play_time`,
  `playguard:<console id>_game_<application id>`), for months of history in a
  *Statistics graph* card.
- **Orders while the console sleeps**: its entities are unavailable then
  (its last will says it is gone), but the actions still send their orders,
  which wait on the broker and are carried out when the console wakes up.
- **Services**: `set_limits`, `add_bonus_time`, `apply_profile`, `stop_today`,
  `lock_now`, `sync_now`, `request_report`.
- An **event entity** for every order handled (applied, refused with the
  reason, waiting for PlayGuard's confirmation), for automations.
- **Diagnostics** with the console's last state and its last diagnostic report.
- An order the console would refuse (read-only mode, orders off, timer writes
  not allowed) is refused here with the reason.

## Requirements

- Home Assistant 2026.10 or newer, with the **MQTT** integration connected to
  the same broker as the console (the Mosquitto add-on, or any other, in
  MQTT 5.0 or 3.1.1: the console speaks 5.0 and falls back to 3.1.1).
  Home Assistant's MQTT integration moves to 5.0 by itself when the broker
  takes it, else it raises a repair, *MQTT protocol migration failed*
  (Home Assistant drops 3.1.1 in 2027.1).
- PlayGuard with *Preferences › Remote access* set up: see PlayGuard's
  [Home Assistant guide](https://github.com/JigSawFr/PlayGuard/blob/main/docs/home-assistant.md).

## Install

With [HACS](https://hacs.xyz/): *HACS › ⋮ › Custom repositories*, add
`https://github.com/JigSawFr/playguard-ha` as an *Integration*, then install
**PlayGuard** and restart Home Assistant.

By hand: copy `custom_components/playguard` into your configuration's
`custom_components` folder and restart.

## Set up

Once installed, each console that publishes (PlayGuard open, or its agent
running) shows up in *Settings › Devices & services › Discovered*: confirm it.
To add one by hand: *Add integration › PlayGuard*, with its id from
*Preferences › Remote access › Console id* (and the topic prefix, `playguard`
unless `sync.conf` says otherwise).

**Options**: *Replace the console's own Home Assistant device* (on by
default) turns the console's MQTT discovery off; turned off, the console
publishes its own device again. Removing the integration turns it back on.

**Reconfigure** changes the topic prefix, when `topic_prefix` in the
console's `sync.conf` changes.

## What it does on the broker

It reads `playguard/<id>/state`, `availability`, `activity`,
`activity/<date>`, `names`, `week`, `event` and `report`, and publishes the
same retained scalar orders as the native entities on
`playguard/<id>/<entity>/set` (the console clears each one once handled). The
contract is PlayGuard's
[`docs/sync-protocol.md`](https://github.com/JigSawFr/PlayGuard/blob/main/docs/sync-protocol.md).
Changing the play timer from Home Assistant needs *Orders may change the play
timer* on the console; with the *ask* policy, PlayGuard asks on the console
first.

## Development

```sh
python3.14 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
python -m pytest
```

`custom_components/playguard/entities.py`, with the names in
`translations/` and the icons in `icons.json`, mirrors PlayGuard's entity
table (`source/sync/sync_entities.c`). PlayGuard's host tests export it as
`build/host-tests/sync/entities.json` (`make test`); copy that file to
`tests/fixtures/entities.json` when it changes: `tests/test_parity.py` fails
until this integration follows. `tests/fixtures/state.json` and
`activity.json` are PlayGuard's own examples, from the same folder.

## License

GPLv3 (see [`LICENSE`](LICENSE)), as PlayGuard.

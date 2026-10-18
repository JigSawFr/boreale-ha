# PlayGuard for Home Assistant

[![validate](https://github.com/JigSawFr/playguard-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/JigSawFr/playguard-ha/actions/workflows/validate.yml)
[![latest release](https://img.shields.io/github/v/release/JigSawFr/playguard-ha)](https://github.com/JigSawFr/playguard-ha/releases/latest)
[![HACS: custom](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![quality scale: gold](https://img.shields.io/badge/quality%20scale-gold-d4af37.svg)](custom_components/playguard/quality_scale.yaml)
[![license: GPLv3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)

**English** · [Français](README.fr.md)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=JigSawFr&repository=playguard-ha&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=playguard)

A Home Assistant integration for [PlayGuard](https://github.com/JigSawFr/PlayGuard),
the Nintendo Switch homebrew that manages the console's parental controls
offline: play-time limits, bedtime, restrictions, extra time, the console
lock. PlayGuard publishes the console's state, play time and events on an MQTT
broker on your local network and takes orders from it (*Preferences › Remote
access*, and its optional agent that keeps the link up while PlayGuard is
closed). This integration turns each console into a Home Assistant device:
see the time left, change the limits, give extra time, lock the console, from
a dashboard or an automation.

The console works with Home Assistant **without** this integration: it
publishes Home Assistant's MQTT discovery itself. The integration adds:

- **Found by itself**: every console that publishes on the broker is offered
  for set-up, no id to type.
- **The same entities** as the console's own MQTT device (names, units,
  options), replacing it (no duplicates; turn it back on in the options),
  plus **Online**, **Agent running** and **Play time this week**.
- **Game names** on *Now playing*, and each game's time today and this week as
  attributes.
- **Long-term statistics**: every finished day's total, and each game's,
  imported into the recorder (`playguard:<console id>_play_time`,
  `playguard:<console id>_game_<application id>`), for months of history in a
  *Statistics graph* card.
- **Orders while the console sleeps**: its entities are unavailable then
  (its last will says it is gone), but the actions still send their orders,
  which wait on the broker and are carried out when the console wakes up.
- **Actions**: `set_limits`, `add_bonus_time`, `apply_profile`, `stop_today`,
  `lock_now`, `sync_now`, `request_report`.
- An **event entity** for every order handled (applied, refused with the
  reason, waiting for PlayGuard's confirmation), for automations.
- An order the console would refuse (read-only mode, orders off, timer writes
  not allowed) is refused here, with the reason.
- **Repairs** when you need to act, and **diagnostics** with the console's
  last state and its last diagnostic report, names left out.

**Contents**: [supported devices](#supported-devices) ·
[prerequisites](#prerequisites) · [installation](#installation) ·
[set-up](#set-up) · [options and reconfiguration](#options-and-reconfiguration) ·
[entities](#entities) · [actions](#actions) · [events](#events) ·
[data updates](#data-updates) · [examples](#examples) ·
[use cases](#use-cases) · [known limitations](#known-limitations) ·
[troubleshooting](#troubleshooting) · [removal](#removal) ·
[help, security and contributing](#help-security-and-contributing)

## Supported devices

- **Nintendo Switch** consoles (the original, the OLED model, the Lite)
  running Atmosphère and a PlayGuard that has *Preferences › Remote access*.
  What PlayGuard itself supports is in its
  [compatibility](https://github.com/JigSawFr/PlayGuard/blob/main/docs/compatibility.md)
  page: tested on firmware 22.0.0 to 22.5.0 (Atmosphère 1.11.x); on a newer
  firmware it opens read-only, and every order is refused until a release of
  PlayGuard supports it; before firmware 21.0.0, it has no play timer
  (limits, bedtime, extra time, blocking all games).
- A console's **sysMMC and emuMMC** are two devices: each has its own
  parental controls and its own console id.
- **Not supported**: the Nintendo Switch 2 (there is no Atmosphère for it),
  and a console without PlayGuard. For Nintendo's own Parental Controls app
  and account, see Home Assistant's *Nintendo Switch Parental Controls*
  integration instead.
- **Home Assistant 2026.10 or newer**, and an MQTT broker in version 5.0 or
  3.1.1: the Mosquitto app, or EMQX, HiveMQ, NanoMQ, VerneMQ and others.
  The console speaks 5.0 and falls back to 3.1.1. Home Assistant's MQTT
  integration moves to 5.0 by itself when the broker takes it, else it raises
  a repair, *MQTT protocol migration failed* (Home Assistant drops 3.1.1 in
  2027.1).

## Prerequisites

1. An MQTT broker, and Home Assistant's **MQTT** integration set up on it
   (*Settings › Devices & services › Add integration › MQTT*; with the
   Mosquitto app, it is offered by itself).
2. A broker user for the console (with the Mosquitto app, any Home
   Assistant user can log in: create one named `playguard`).
3. On the console, PlayGuard's link set up on that broker: *Preferences ›
   Remote access › MQTT / Home Assistant* (broker address, port, user name
   and password, the name in Home Assistant), then *Remote link* on. Its
   *Status* reads *Online*. PlayGuard's
   [Home Assistant guide](https://github.com/JigSawFr/PlayGuard/blob/main/docs/home-assistant.md)
   has the details, and the optional agent that keeps the link up while
   PlayGuard is closed.
4. To change the limits, bedtime or extra time from Home Assistant: *Orders
   may change the play timer* on, in the same screen. *Orders received* says
   whether the console asks before carrying an order out (the default), does
   it at once, or refuses it.

## Installation

With [HACS](https://hacs.xyz/):

1. *HACS › ⋮ › Custom repositories*: add
   `https://github.com/JigSawFr/playguard-ha`, type *Integration*; or the
   first button at the top of this page (My Home Assistant opens the
   repository in your HACS). In PlayGuard, *Remote access › Home Assistant ›
   Install the Home Assistant integration* shows the same two buttons as QR
   codes, for a phone.
2. Open **PlayGuard** in HACS and *Download* it: HACS installs the
   `playguard.zip` of the release you pick.
3. Restart Home Assistant.

By hand: download `playguard.zip` from the
[latest release](https://github.com/JigSawFr/playguard-ha/releases/latest),
extract it into a `custom_components/playguard` folder of your configuration,
and restart Home Assistant. Each release's zip carries a build provenance
attestation: `gh attestation verify playguard.zip -R JigSawFr/playguard-ha`
checks that it was built by this repository's CI (`SHA256SUMS.txt`, next to
it, has its checksum).

## Set-up

**Found on the broker.** Each console that publishes (PlayGuard open, or its
agent running) shows up in *Settings › Devices & services › Discovered*:

1. Select **PlayGuard** under *Discovered*.
2. Confirm the console (its name and id are shown). Nothing to type.

**By hand** (a console that is not found, or a prefix other than
`playguard`):

1. *Settings › Devices & services › Add integration › PlayGuard*.
2. Fill in the fields below, then *Submit*. The integration waits up to
   10 seconds for the console's state on the broker, and creates the entry
   with the console's name; nothing there, it says so and lets you correct
   the fields.

| Field | What to put |
|---|---|
| **Console id** | The console's 8 characters (0 to 9, a to f), from PlayGuard › *Preferences › Remote access › Console id*. |
| **Topic prefix** | `playguard`, unless `topic_prefix` in the console's `sync.conf` says otherwise. |

Each console is one entry and one device; the same console cannot be added
twice.

## Options and reconfiguration

*Settings › Devices & services › PlayGuard › ⚙ (Configure)*:

| Option | Default | What it does |
|---|---|---|
| **Replace the console's own Home Assistant device** | on | Turns the console's MQTT discovery off, so its entities are not there twice. Off: the console publishes its own device again (next to this one). The entry reloads when it changes. |

*⋮ › Reconfigure* changes the **Topic prefix**, when `topic_prefix` in the
console's `sync.conf` changes. As when adding a console by hand, the console
must answer under the new prefix; the entry then reloads.

A console moved back to the prefix `playguard` is found again by discovery,
and its entry follows it (and reloads) once the console publishes a state
newer than the last one the entry read; a state left on the broker under the
former prefix does not move it back.

## Entities

One device per console, named after the console (*Name in Home Assistant*
in PlayGuard), with its firmware and PlayGuard's version. *Config* and
*diagnostic* entities are in their own sections of the device page and out of
the default dashboards. All are unavailable while the console is offline,
except *Online*.

**Binary sensors**

| Entity | What it says | Notes |
|---|---|---|
| Parental controls | Parental controls are set on the console. | |
| Temporarily unlocked | Parental controls are unlocked for now (the PIN was entered). | lock device class: *unlocked* when on |
| Companion app linked | Nintendo's phone app is linked to the console. | |
| Play timer | The daily play-time limit is on. | |
| Time is up | Today's limit is reached. | |
| PIN set | A PIN is set. | diagnostic |
| Network clock accurate | The console's clock is set from the network. | diagnostic |
| Online | The console is on the broker now (off: asleep, off, out of reach). | diagnostic, this integration's |
| Agent running | PlayGuard's agent keeps the link up. | diagnostic, disabled by default, this integration's |

**Sensors** (minutes)

| Entity | What it says | Notes |
|---|---|---|
| Used screen time | Today's play time, as the play timer counts it. | daily total, back to 0 at midnight |
| Used screen time (play log) | Today's play time from the play log, with each game's minutes (`games`). | daily total |
| Screen time remaining | What is left of today's limit. | |
| Extended screen time | Extra time granted today. | |
| Play time this week | The last 7 days, with each day's (`days`) and each game's (`games`) minutes. | this integration's; once PlayGuard itself has run |
| Now playing | The game being played, by name (attributes `app_id`, `since`). | unknown while PlayGuard is open (nobody plays then) |
| Age rating | The age rating of the restriction level. | diagnostic |
| Firmware, Atmosphère | The console's versions. | diagnostic |
| Last order | The last order handled, and how. | diagnostic |
| Time spent (1952) | The play timer's raw count. | diagnostic, disabled by default |

**Numbers** (config, minutes, 0 to 1440; 1440 means no limit):
*Limit Sunday* … *Limit Saturday*, *Limit every day* (unknown when the days
differ), *Max screentime today* (today only; the usual limit comes back
tomorrow).

**Time** (config): *Bedtime alarm* (when the alarm sounds), *Bedtime end
time* (when play is allowed again).

**Switches**: *Block all games* (no play at all), *Unlocked* (off locks parental
controls again after a temporary unlock); config: *Bedtime alarm enabled*,
*Time's up alarm*, *VR mode restricted*, *Posting to social media
restricted*, *Communication restricted*.

**Selects** (config): *Restriction level* (unrestricted, young child, child,
teen, custom), *Profile* (applies one of the profiles saved in PlayGuard; it
shows no current choice: the limits say which one is in effect).

**Buttons**: *Extra time +15 min*, *+30 min*, *+1 h*, *No more play today*,
*Remove the limit*, *Turn parental controls back on* (after a temporary unlock);
diagnostic: *Sync now* (the console publishes everything again), *Export a
diagnostic report*.

**Event**: *Events*, see [events](#events).

**The console itself** (`playguard/<id>/system`, kept fresh by the agent
while PlayGuard is closed):

| Entity | What it says | Notes |
|---|---|---|
| Battery, Charging, Docked | Its charge, whether a charger gives power, whether it is docked. | |
| SD card free space, Internal storage free space | MiB left on the SD card and on the system's user storage (the emuMMC's on an emuMMC). | read every 5 minutes; their sizes are diagnostic |
| Model | Switch (2017), Switch (2019), Switch Lite, Switch OLED. | diagnostic |
| Console nickname, Region, System, hekate | System Settings' nickname, the region, sysMMC or emuMMC, hekate on the SD card. | diagnostic |
| PRODINFO blanked | Atmosphère hides the console's identity. | diagnostic |
| Temperature, Connection, IP address, Wi-Fi signal | The internal sensor, Wi-Fi or ethernet, the console's address, 0–3 bars. | diagnostic |
| Last started | When the console started (not when it last woke up). | diagnostic |
| Serial number | The console's real serial number (from Atmosphère's backup when PRODINFO is blanked). | diagnostic, disabled by default; only with *Publish the serial number* on the console |
| Wi-Fi network | The network's name. | diagnostic, disabled by default |

**Games** (`playguard/<id>/games`, which PlayGuard publishes after each read
of the play log): *Games installed*, *Play time (all time)* (every game,
every account), *User accounts* (diagnostic); and **one sensor per game**,
*Play time · <game>*: its minutes since it was first played (a growing total,
for the long-term statistics), with attributes `installed`, `version`,
`launches`, `first_played`, `last_played`. A game's sensor appears when the
console first lists it, and stays when the game is uninstalled (with
`installed: false`); one the console no longer lists is unavailable.

The entities that change the play timer (limits, bedtime, extra time,
blocking all games, profiles) need *Orders may change the play timer* on the
console; without it, they are refused here with the reason. Turning parental controls back on
(*Unlocked* off) and the restrictions do not need it.

Home Assistant builds the entity ids itself, from the device's and the
entities' names, when they are first registered, and you can change them: they
may differ from those of the console's own MQTT device, so check the
automations that used those.

## Actions

Each action takes the console's **device** (`device_id`), and sends a retained
order: when the console is asleep, it waits on the broker and is carried out
when the console wakes up. An order the console would refuse is refused at
once, with the reason (read-only mode, orders refused, timer writes off, an
unknown profile, a device that is not a loaded PlayGuard console).

| Action | Fields | What it does |
|---|---|---|
| `playguard.set_limits` | `minutes` (0 to 1440; 1440 = no limit), `day` (`all`, the default, `today`, or `sun` … `sat`), or `week` (seven limits, Sunday first, in place of `minutes` and `day`) | Sets a day's limit, every day's, today's only, or the whole week's. |
| `playguard.add_bonus_time` | `minutes` (5 to 180, default 30) | Extra minutes today; the usual limit comes back tomorrow. |
| `playguard.apply_profile` | `profile` (its name in PlayGuard) | Applies the limits of a saved profile. |
| `playguard.stop_today` | | 0 minutes today; the usual limit comes back tomorrow. |
| `playguard.lock_now` | | Turns parental controls back on after a temporary unlock. |
| `playguard.sync_now` | | The console publishes everything again. |
| `playguard.request_report` | | The console saves a diagnostic report on its SD card, and publishes it when *Remote access* allows it (then in the device's diagnostics). |

`set_limits`, `add_bonus_time`, `apply_profile` and `stop_today` need
*Orders may change the play timer*.

## Events

The *Events* entity fires once per order the console handled, with one of
these event types:

| Event type | When |
|---|---|
| `command_applied` | The order was carried out. |
| `command_rejected` | The order was refused; `reason` says why (`policy_off`, `timer_writes_disabled`, `read_only`, `not_confirmed`, `out_of_range`, `no_such_profile` …, see PlayGuard's [protocol](https://github.com/JigSawFr/PlayGuard/blob/main/docs/sync-protocol.md)). |
| `command_waiting` | The order waits for PlayGuard (the agent keeps it until PlayGuard confirms it, under *Ask on the console*). |

Attributes: `entity` (the order's entity), `payload` (its value), `reason`,
`rc` (the console's result code, `0x…`, when it answered), `source` (`app`
or `agent`), `ts` (when, POSIX time). Events are not retained: one sent while
Home Assistant was away is not seen; *Last order* keeps the last result.

## Data updates

Nothing is polled: the console pushes over MQTT, and Home Assistant only
listens.

- The console publishes its **state** when it changes, and every `poll_s`
  seconds for a fresh time stamp (30 by default, 10 to 300, in its
  `sync.conf`). While PlayGuard is closed, the agent reads the console every
  `poll_s` seconds.
- Everything but the events is **retained** on the broker: after a restart of
  Home Assistant, the last documents arrive at once, even from a sleeping
  console.
- **Availability** is the console's last will: a console that falls asleep or
  drops off the network is marked offline within about 45 seconds (keep-alive
  30 s). The integration logs it once when it goes, once when it is back.
- Today's **play log** (`activity`) comes with the state; a finished day
  (`activity/<date>`) at the first cycle after midnight, the console keeping
  the last 14. The **game names** and the **week** come when PlayGuard itself
  runs (not the agent).
- **Statistics**: the finished days are imported 5 seconds after the last one
  arrives (they come in a burst); importing a day again replaces it.
- **Orders** are retained until the console handles them; it then clears
  them, publishes an event and its new state.
- **The integration's version**: at each set-up of a console's entry (so at
  each start of Home Assistant), the integration publishes its version and
  Home Assistant's, retained, on `playguard/<id>/integration`. PlayGuard
  shows it in *Remote access › Home Assistant* and, when it checks for
  updates, says in its notifications that a newer release of the integration
  is out, with what changed and the QR code that opens it in HACS.

## Examples

Entity ids depend on the console's name (here *Living room*): check them on
the device's page. The actions' device is picked in the UI; in YAML, it is the
device's id (on the device page, *⋮ › Device info*, or in the URL).

A notification when an order is refused:

```yaml
alias: PlayGuard order refused
triggers:
  - trigger: state
    entity_id: event.living_room_events
conditions:
  - condition: state
    entity_id: event.living_room_events
    attribute: event_type
    state: command_rejected
actions:
  - action: notify.notify
    data:
      message: >-
        PlayGuard refused {{ trigger.to_state.attributes.entity }}:
        {{ trigger.to_state.attributes.reason }}
```

Time is up: say so on the phone.

```yaml
alias: Switch time is up
triggers:
  - trigger: state
    entity_id: binary_sensor.living_room_time_is_up
    to: "on"
actions:
  - action: notify.notify
    data:
      message: "No more Switch today: the limit is reached."
```

The holidays' limits from a calendar, the school week's after:

```yaml
alias: Holidays limits
triggers:
  - trigger: calendar
    event: start
    entity_id: calendar.school_holidays
  - trigger: calendar
    event: end
    entity_id: calendar.school_holidays
actions:
  - action: playguard.apply_profile
    data:
      device_id: 0123456789abcdef0123456789abcdef
      profile: "{{ 'Holidays' if trigger.event == 'start' else 'School week' }}"
```

Extra time for the chores done:

```yaml
alias: Chores done, 30 minutes more
triggers:
  - trigger: state
    entity_id: input_boolean.chores_done
    to: "on"
actions:
  - action: playguard.add_bonus_time
    data:
      device_id: 0123456789abcdef0123456789abcdef
      minutes: 30
  - action: input_boolean.turn_off
    target:
      entity_id: input_boolean.chores_done
```

A dashboard button for 30 minutes more:

```yaml
type: button
name: +30 min
icon: mdi:timer-plus-outline
tap_action:
  action: perform-action
  perform_action: button.press
  target:
    entity_id: button.living_room_extra_time_30_min
```

## Use cases

- See at a glance how long the children played today and what is left, on
  the family dashboard or a phone.
- Give extra time, stop play for today or lock the console from the sofa or
  from work, without picking up the console or the PIN.
- Switch between a school-week and a holidays profile from a calendar, or
  set the weekend limits on Friday evening.
- Reward chores or homework with extra time, through a button or a helper.
- Get told when the time is up, when an order is refused, or when the
  console has been on past bedtime.
- Keep months of play history, per day and per game, in a *Statistics graph*
  card, long after the console forgot them.

## Known limitations

- PlayGuard runs on a console with custom firmware (Atmosphère); there is
  none for the Nintendo Switch 2.
- Some things are never possible from Home Assistant, by PlayGuard's design:
  reading, setting or changing the PIN, deleting parental controls, unlinking
  the phone app.
- While the console is offline its entities are unavailable: only the
  actions can send orders then, and these wait for the console. Under *Ask
  on the console*, an order also waits for someone to confirm it on the
  console (event `command_waiting`); under *Refuse them*, nothing is applied.
- Without *Orders may change the play timer*, the limits, bedtime, extra time,
  blocking all games and the profiles are refused (the console's own device
  hides these entities instead).
- Only the prefix `playguard` is discovered; a console under another prefix
  is added by hand.
- *Now playing* is unknown while PlayGuard is open (and filled by the agent
  otherwise); the week and the game names need PlayGuard itself to have run.
- The statistics only have the finished days the console still held (the
  last 14) once the integration was set up.
- The entity ids may differ from those of the console's own MQTT device.
- *Profile* has no current choice: the console does not say which profile is
  in effect.

## Troubleshooting

<details>
<summary>No PlayGuard console in <em>Discovered</em></summary>

The console publishes nothing on the broker Home Assistant uses, or under
another prefix. On the console, *Preferences › Remote access › Status* must
read *Online* (PlayGuard open, or its agent running), with the same broker as
Home Assistant's MQTT integration. A prefix other than `playguard` is never
discovered: add the console by hand.
</details>

<details>
<summary>"This console has published nothing on the broker under this prefix."</summary>

When adding by hand or reconfiguring, no state came from that console id
under that prefix. Check the id (*Remote access › Console id*: the emuMMC's
differs from the sysMMC's), the prefix (`topic_prefix` in `sync.conf`), and
that the console's link was online at least once on this broker.
</details>

<details>
<summary>"The MQTT integration is not set up yet"</summary>

PlayGuard talks to Home Assistant through the MQTT integration: set it up
first, on the same broker as the console, then add PlayGuard.
</details>

<details>
<summary>Every entity is unavailable</summary>

The console is offline (*Online* is off): asleep, turned off, out of Wi-Fi,
or PlayGuard closed without its agent. The entities come back when it is
online again. Orders sent through the actions meanwhile wait on the broker.
</details>

<details>
<summary>"Orders may not change the play timer …" / "The console refuses orders …" / "PlayGuard is in read-only mode on this console …"</summary>

The console would refuse the order, so Home Assistant does not send it. Turn
on *Orders may change the play timer*, or set *Orders received* to something
other than *Refuse them*, in PlayGuard › *Preferences › Remote access*.
Read-only mode means a firmware PlayGuard does not support yet: update
PlayGuard.
</details>

<details>
<summary>An order is sent but nothing happens</summary>

Under *Ask on the console*, PlayGuard asks on the console before carrying it
out (event `command_waiting` when the agent keeps it). A sleeping console
carries it out when it wakes up. *Last order* and the *Events* entity say
what became of it.
</details>

<details>
<summary>Repair: "… publishes its own Home Assistant device again"</summary>

The console's own MQTT device is back next to this integration's, so every
entity is there twice. The repair asks the console again to turn it off. If
it comes back, update PlayGuard, or turn off *Create the device in Home
Assistant (MQTT discovery)* in PlayGuard › *Preferences › Remote access*. To
keep the console's own device instead, turn off the option *Replace the
console's own Home Assistant device*.
</details>

<details>
<summary>Repair: "… speaks a newer PlayGuard protocol"</summary>

The console's PlayGuard is newer than this integration: update the PlayGuard
integration (HACS). Until then, some values may be missing.
</details>

<details>
<summary>The statistics graph is empty</summary>

The statistics need the recorder (on by default), and only hold finished
days: the first appears after the console's first cycle past midnight. Pick
the statistic `playguard:<console id>_play_time` (or a game's) in a
*Statistics graph* card.
</details>

For anything else, download the diagnostics (*Settings › Devices & services
› PlayGuard › ⋮ › Download diagnostics*: the console's last documents and
report, names left out) and open an
[issue](https://github.com/JigSawFr/playguard-ha/issues).

## Removal

1. *Settings › Devices & services › PlayGuard*, then for each console *⋮ ›
   Delete*. Removing a console's entry asks the console to publish its own
   Home Assistant device again (a sleeping console does it when it wakes up),
   and clears the integration's version on the broker (PlayGuard no longer
   warns of its releases); to do without the console's own device, turn off
   *Create the device in Home Assistant* in PlayGuard.
2. With HACS: *HACS › PlayGuard › ⋮ › Remove*; by hand: delete
   `custom_components/playguard`. Restart Home Assistant.
3. The long-term statistics stay in the recorder: delete them in *Settings ›
   Tools › Statistics* if you do not want them any more.

Nothing else is left on the broker: the console clears each order once
handled. To stop the console publishing at all, turn *Remote link* off in
PlayGuard.

## What it does on the broker

It reads `playguard/<id>/state`, `system`, `games`, `availability`, `activity`,
`activity/<date>`, `names`, `week`, `event` and `report`, and publishes the
same retained scalar orders as the native entities on
`playguard/<id>/<entity>/set` (the console clears each one once handled), and
its version, retained, on `playguard/<id>/integration`. The contract is
PlayGuard's
[`docs/sync-protocol.md`](https://github.com/JigSawFr/PlayGuard/blob/main/docs/sync-protocol.md).

## Help, security and contributing

- A problem with the integration: [Getting help](.github/SUPPORT.md) says
  where to ask; a bug report wants the console's diagnostics (the device's
  page, *⋮ › Download diagnostics*: names and account ids left out).
- A security problem: privately, as [SECURITY.md](SECURITY.md) says, never in
  a public issue.
- Working on the integration (tests, coverage, the quality scale, the parity
  with PlayGuard's entity table, translations, releases):
  [CONTRIBUTING.md](CONTRIBUTING.md). Changes are listed in
  [CHANGELOG.md](CHANGELOG.md).
- Support PlayGuard: [GitHub Sponsors](https://github.com/sponsors/JigSawFr)
  or [Ko-fi](https://ko-fi.com/jigsawfr).

## License

GPLv3 (see [`LICENSE`](LICENSE)), as PlayGuard.

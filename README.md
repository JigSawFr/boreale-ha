<div align="center">

<img src="https://raw.githubusercontent.com/JigSawFr/playguard-ha/main/.github/readme/banner.png" alt="PlayGuard for Home Assistant" width="100%">

### Nintendo Switch parental controls, in Home Assistant

**Play&nbsp;time · Limits · Extra&nbsp;time · Bedtime · Statistics · Local&nbsp;MQTT**

[![validate](https://github.com/JigSawFr/playguard-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/JigSawFr/playguard-ha/actions/workflows/validate.yml)
[![latest release](https://img.shields.io/github/v/release/JigSawFr/playguard-ha)](https://github.com/JigSawFr/playguard-ha/releases/latest)
[![HACS: custom](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![quality scale: platinum](https://img.shields.io/badge/quality%20scale-platinum-a8b5c5.svg)](https://github.com/JigSawFr/playguard-ha/blob/main/custom_components/playguard/quality_scale.yaml)
[![license: GPLv3](https://img.shields.io/badge/license-GPLv3-blue.svg)](https://github.com/JigSawFr/playguard-ha/blob/main/LICENSE)

**English** · [Français](https://github.com/JigSawFr/playguard-ha/blob/main/README.fr.md)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=JigSawFr&repository=playguard-ha&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=playguard)

[**Install**](#-installation) ·
[**Set&nbsp;up**](#-set-up) ·
[**Entities**](#-entities) ·
[**Examples**](#-examples) ·
[**PlayGuard**](https://github.com/JigSawFr/PlayGuard)

<img src="https://raw.githubusercontent.com/JigSawFr/playguard-ha/main/.github/readme/dashboard.png" alt="A family dashboard: today's play time and what is left, the game being played, extra time in one tap, the last two weeks per child, the rules" width="100%">

</div>

---

A Home Assistant integration for [PlayGuard](https://github.com/JigSawFr/PlayGuard),
the Nintendo Switch homebrew that manages the console's parental controls
offline: play-time limits, bedtime, restrictions, extra time, the console
lock. PlayGuard publishes the console's state, play time and events on an MQTT
broker on your local network and takes orders from it (*Console › Remote
access*, and its optional agent that keeps the link up while PlayGuard is
closed). This integration turns each console into a Home Assistant device:
see the time left, change the limits, give extra time, lock the console, from
a dashboard or an automation.

## ✨ Features

The console works with Home Assistant **without** this integration: it
publishes Home Assistant's MQTT discovery itself. The integration adds:

- **Found by itself**: every console that publishes on the broker is offered
  for set-up, no id to type.
- **The same entities** as the console's own MQTT device (names, units,
  options), replacing it (no duplicates; turn it back on in the options),
  plus **Online**, **Agent running**, **Play time this week**, **Play ends**
  and the **Play sessions** calendar.
- **Game names** on *Now playing*, and each game's time today and this week as
  attributes; every game on *Games installed* (`games`), with its play time:
  one entity for the games, not one per game.
- **Each account's play time** (each child's): a sensor for today and one
  for this week per account, named after the account on the console, and
  both as attributes of the console's play time.
- **Long-term statistics**: every finished day's total, each game's and each
  account's, imported into the recorder (`playguard:<console id>_play_time`,
  `playguard:<console id>_game_<application id>`,
  `playguard:<console id>_account_<account id>`), for months of history in a
  *Statistics graph* card.
- **Orders while the console sleeps**: its entities keep their last values
  (*Online* says it is gone), and a change made to a control or an action
  waits on the broker and is carried out when the console wakes up.
- **Actions**: `set_limits`, `add_bonus_time`, `apply_profile`, `stop_today`,
  `lock_now`, `sync_now`, `request_report`, `get_play_time`.
- An **event entity** for every order handled (applied, refused with the
  reason, waiting for PlayGuard's confirmation), for automations.
- **Triggers and conditions** of its own in the automation editor: a game
  started or stopped, time running out, games blocked, an order refused; a
  game played, the limit reached, parental controls on.
- **Assist and AI assistants**: today's play time, extra time, no more play
  today, by voice or chat; `get_play_time` returns the day's or the week's
  play time to a script.
- An order the console would refuse (read-only mode, orders off, timer writes
  not allowed) is refused here, with the reason.
- **The console's answer**: an order the console refuses makes its action
  fail, with the console's reason; one refused later (sent while it slept, or
  waiting for PlayGuard) raises a notification.
- **Repairs** when you need to act, and **diagnostics** with the console's
  last state and its last diagnostic report, names left out.

<details>
<summary><b>📸 Screenshots</b></summary>
<br>

<p align="center">
  <img src="https://raw.githubusercontent.com/JigSawFr/playguard-ha/main/.github/readme/device.png" alt="The console's device page: its controls, sensors and activity" width="72%">
  <img src="https://raw.githubusercontent.com/JigSawFr/playguard-ha/main/.github/readme/phone.png" alt="The family dashboard on a phone" width="24%">
  <br><sub><b>The console's device</b> · <b>On a phone</b></sub>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/JigSawFr/playguard-ha/main/.github/readme/discovered.png" alt="A console found on the broker, offered under Discovered" width="72%">
  <br><sub><b>Found on the broker</b></sub>
</p>

<sub>A demo console in Home Assistant 2026.10, dark theme; the dashboard is the family dashboard of the examples below, per child added.</sub>

</details>

**Contents**: [supported devices](#-supported-devices) ·
[prerequisites](#-prerequisites) · [installation](#-installation) ·
[set-up](#-set-up) · [options and reconfiguration](#-options-and-reconfiguration) ·
[entities](#-entities) · [actions](#-actions) · [events](#-events) ·
[triggers and conditions](#-triggers-and-conditions) ·
[Assist and AI assistants](#-assist-and-ai-assistants) ·
[data updates](#-data-updates) · [examples](#-examples) ·
[use cases](#-use-cases) · [known limitations](#-known-limitations) ·
[troubleshooting](#-troubleshooting) · [removal](#-removal) ·
[help, security and contributing](#-help-security-and-contributing)

## 🎮 Supported devices

- **Nintendo Switch** consoles (the original, the OLED model, the Lite)
  running Atmosphère and a PlayGuard that has *Console › Remote access*.
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

## ✅ Prerequisites

1. An MQTT broker, and Home Assistant's **MQTT** integration set up on it
   (*Settings › Devices & services › Add integration › MQTT*; with the
   Mosquitto app, it is offered by itself).
2. A broker user for the console (with the Mosquitto app, any Home
   Assistant user can log in: create one named `playguard`).
3. On the console, PlayGuard's link set up on that broker: *Console ›
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

## 📦 Installation

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

A new release shows up in HACS by itself, within a few hours (HACS checks
GitHub on a schedule); to see it at once, *HACS › PlayGuard › ⋮ › Update
information*. Then *Update*, and restart Home Assistant.

By hand: download `playguard.zip` from the
[latest release](https://github.com/JigSawFr/playguard-ha/releases/latest),
extract it into a `custom_components/playguard` folder of your configuration,
and restart Home Assistant. Each release's zip carries a build provenance
attestation: `gh attestation verify playguard.zip -R JigSawFr/playguard-ha`
checks that it was built by this repository's CI (`SHA256SUMS.txt`, next to
it, has its checksum).

## 🔌 Set-up

**Found on the broker.** Each console that publishes (PlayGuard open, or its
agent running) shows up in *Settings › Devices & services › Discovered*:

1. Select **PlayGuard** under *Discovered*.
2. Confirm the console (its name and id are shown). Nothing to type.

**By hand** (a console that is not found, or a prefix other than
`playguard`):

1. *Settings › Devices & services › Add integration › PlayGuard*.
2. The integration listens to the broker for a few seconds, and lists the
   consoles whose state is there and that are not set up yet (their name, id,
   and prefix when it is not `playguard`; under a prefix of one or two
   levels). Pick one: it is added.
3. None found, or *Another console, by its id*: fill in the fields below,
   then *Submit*. The integration waits up to 10 seconds for the console's
   state on the broker, and creates the entry with the console's name;
   nothing there, it says so and lets you correct the fields.

| Field | What to put |
|---|---|
| **Console id** | The console's 8 characters (0 to 9, a to f), from PlayGuard › *Console › Remote access › Console id*. |
| **Topic prefix** | `playguard`, unless `topic_prefix` in the console's `sync.conf` says otherwise. |

Each console is one entry and one device; the same console cannot be added
twice.

## 🔧 Options and reconfiguration

*Settings › Devices & services › PlayGuard › ⚙ (Configure)*:

| Option | Default | What it does |
|---|---|---|
| **Replace the console's own Home Assistant device** | on | Turns the console's MQTT discovery off, so its entities are not there twice. Off: the console publishes its own device again (next to this one). The entry reloads when it changes. |
| **Keep the last values while the console sleeps** | on | While the console is offline (asleep, off, out of reach), its entities keep showing what it last said, controls included: a change made to one waits on the broker and is carried out when the console wakes up. Off: every entity but *Online* is unavailable then. |
| **Notify an order refused later** | on | An order whose answer comes after its action returned (sent while the console slept, or waiting for PlayGuard's confirmation) and that the console refuses raises a notification, with the reason; the next order applied takes it away. A refusal that comes while the action still waits makes the action fail, whatever this option. |

*⋮ › Reconfigure* changes the **Topic prefix**, when `topic_prefix` in the
console's `sync.conf` changes. As when adding a console by hand, the console
must answer under the new prefix; the entry then reloads.

A console moved back to the prefix `playguard` is found again by discovery,
and its entry follows it (and reloads) once the console publishes a state
newer than the last one the entry read; a state left on the broker under the
former prefix does not move it back.

## 🧩 Entities

One device per console, named after the console (*Name in Home Assistant*
in PlayGuard): the console as Nintendo names it, its model and model number
(*Nintendo Switch – OLED Model*, HEG-001) and the system it runs as its
software (*23.0.1 · Atmosphère 1.10.1*). *Config* and
*diagnostic* entities are in their own sections of the device page and out of
the default dashboards. While the console is offline, its entities keep their
last values (*Online* says it is offline); with the option *Keep the last
values while the console sleeps* off, all but *Online* are unavailable.

As on the console's own device, what few dashboards need is **disabled by
default** (marked so below): turn one on from the device page (*… entities
not shown*), and the entry reloads with it.

**Binary sensors**

| Entity | What it says | Notes |
|---|---|---|
| Parental controls set up | Parental controls are set on the console. | |
| Companion app linked | Nintendo's phone app is linked to the console. | |
| Play timer | The daily play-time limit is on. | |
| Playing blocked | The play timer blocks games: today's limit is reached, or it is bedtime. | its `reason`: `limit` or `bedtime` |
| PIN set | A PIN is set. | diagnostic |
| Network clock accurate | The console's clock is set from the network. | diagnostic, disabled by default |
| Online | The console is on the broker now (off: asleep, off, out of reach). | diagnostic, this integration's |
| Agent running | PlayGuard's agent keeps the link up (off while the console is offline: it sleeps with it). | diagnostic, disabled by default, this integration's |

**Lock**: *Parental controls*, locked while they are in effect. Unlock it to
unlock them for now with the PIN PlayGuard keeps (it needs *Orders may change
the play timer*); lock it to turn them back on, always allowed.

**Sensors** (minutes; the week and all time are shown in hours)

| Entity | What it says | Notes |
|---|---|---|
| Play time today | Today's play time from the play log (every game, with or without a limit), with each game's minutes (`games`) and each account's (`accounts`). | daily total, back to 0 at midnight; `accounts` only when PlayGuard read the accounts (its Activity tab's account filter), else none |
| Used screen time | Today's play time, as the play timer counts it (only while a limit is set). | daily total, disabled by default |
| Screen time remaining | What is left of today's limit. | |
| Extended screen time | Extra time granted today. | |
| Play time this week | The last 7 days, with each day's (`days`), each game's (`games`) and each account's (`accounts`) minutes. | this integration's; once PlayGuard or its agent has published play time |
| Play ends | While a game is played, when play has to stop: the end of today's limit or bedtime, whichever comes first (attribute `ends_by`: `limit` or `bedtime`). For a countdown on a dashboard, a watch or a Live Activity. | this integration's; unknown when no game is played, when games are already blocked, with the play timer off, or with neither a limit nor bedtime |
| *Account*'s play time today, *Account*'s play time this week | One pair per user account, created as the console speaks of it (its name, or its play time). Minutes, the week's shown in hours. | this integration's; unknown when nobody's time was read (the app reads the accounts when asked, the agent from the play log) |
| Play sessions (calendar) | Each game played and when: one event per stretch the game was in front while the console was online, named after the game; the one going on reads *on*. Built from the recorder's history of *Now playing* and *Online*, so it goes back as far as the recorder keeps them (10 days by default). | this integration's; empty without the recorder or with *Now playing* off |
| Last seen | When the console last said something (its state comes every 30 s while it is awake). | diagnostic, this integration's |
| Now playing | The game being played, by name (attributes `app_id`, `since`). | unknown while PlayGuard is open (nobody plays then) |
| Age rating | The age rating of the restriction level. | diagnostic, disabled by default |
| Firmware, Atmosphère | The console's versions (the device's info shows them too). | diagnostic, disabled by default |
| Last order | The last order handled, and how. | diagnostic, disabled by default |
| Time spent (1952) | The play timer's raw count. | diagnostic, disabled by default |

**Numbers** (config, minutes, 0 to 1440; 1440 means no limit): *Limit every
day* (unknown when the days differ), *Max screentime today* (today only; the
usual limit comes back tomorrow), *Limit Sunday* … *Limit Saturday*
(disabled by default).

**Time** (config): *Bedtime* (when the alarm sounds), *Wake-up time* (when
play is allowed again).

**Switches**: *Block all games* (no play at all); config: *Bedtime alarm*,
*Time's up alarm*, *VR mode restricted*, *Posting to social media
restricted*, *Communication restricted*.

**Selects** (config): *Restriction level* (unrestricted, young child, child,
teen, custom), *Profile* (applies one of the profiles saved in PlayGuard, and
shows the one in effect: the saved profile whose limits are the console's;
unknown when none is).

**Buttons**: *Extra time +15 min*, *+30 min*, *+1 h*, *No more play today*,
*Remove the limit*; diagnostic: *Sync now* (the console publishes everything
again), *Export a diagnostic report* (disabled by default).

**Event**: *Events*, see [events](#-events).

**The console itself** (`playguard/<id>/system`, kept fresh by the agent
while PlayGuard is closed):

| Entity | What it says | Notes |
|---|---|---|
| Battery, Charging, Docked | Its charge, whether a charger gives power, whether it is docked. | |
| SD card free space, Internal storage free space | The space left on the SD card and on the system's user storage (the emuMMC's on an emuMMC), shown in GiB. | read every 5 minutes; their sizes are diagnostic, disabled by default |
| Model | Switch (2017), Switch (2019), Switch Lite, Switch OLED. | diagnostic, disabled by default |
| Console nickname, Region, System, hekate | System Settings' nickname, the region, sysMMC or emuMMC, hekate on the SD card. | diagnostic, disabled by default |
| PRODINFO blanked | Atmosphère hides the console's identity. | diagnostic, disabled by default |
| Temperature, Connection, IP address, Wi-Fi signal | The internal sensor, Wi-Fi or ethernet, the console's address, 0–3 bars. | diagnostic, disabled by default |
| Last started | When the console started (not when it last woke up). | diagnostic, disabled by default |
| Serial number | The console's real serial number (from Atmosphère's backup when PRODINFO is blanked). | diagnostic, disabled by default; only with *Publish the serial number* on the console |
| Wi-Fi network | The network's name. | diagnostic, disabled by default |

**Games** (`playguard/<id>/games`, which PlayGuard publishes after each read
of the play log): *Games installed*, with every game the console lists in
`games` (the last played first: `app_id`, `name`, `minutes`, `installed`,
`last_played`; not recorded), *Play time (all time)* (every game, every
account), *User accounts* (diagnostic, disabled by default).

There is **no sensor per game**: a game's time today is in the play log's
`games` attribute, this week's in *Play time this week*'s, since it was first
played in *Games installed*'s, and its history in its long-term statistic
(above). 0.3 had a sensor per game; updating removes them (and their option),
and the statistics stay. For an automation on one game, a template reads the
attribute:

```jinja
{{ (state_attr('sensor.living_room_play_time_today', 'games') or {})
   .get('Super Mario Odyssey', 0) > 60 }}
```

The entities that change the play timer (limits, bedtime, extra time,
blocking all games, profiles) need *Orders may change the play timer* on the
console; without it, they are refused here with the reason, and so is
unlocking the lock. Locking it again and the restrictions do not need it.

**What PlayGuard publishes**: its *Remote access › What is published* turns
off the play time, the games, the console's state, the network, the versions
and hardware, the serial number or the reports. Their entities then leave
Home Assistant (and are not created again at the next start); turned back
on, the entry reloads and they come back. The parental controls are always
published.

0.5 replaces *Unlocked*, *Turn parental controls back on* and *Temporarily
unlocked* with the lock: updating removes them, so check the automations that
used them.

Home Assistant builds the entity ids itself, from the device's and the
entities' names, when they are first registered, and you can change them: they
may differ from those of the console's own MQTT device, so check the
automations that used those.

## ⚡ Actions

Each action takes the console's **device** (`device_id`), and sends a retained
order: when the console is asleep, it waits on the broker and is carried out
when the console wakes up. An order the console would refuse is refused at
once, with the reason (read-only mode, orders refused, timer writes off, an
unknown profile, a device that is not a loaded PlayGuard console).

While the console is online, the action (and a change made to an entity)
waits up to 10 seconds for its answer. Refused, it fails with the console's
reason (*Salon refused this order: the bedtime alarm is off.*), shown under the
control, and an automation sees the error. Applied, waiting for PlayGuard's
confirmation, or no answer in time: it returns; a refusal that comes later
raises a notification (option *Notify an order refused later*).

| Action | Fields | What it does |
|---|---|---|
| `playguard.set_limits` | `minutes` (0 to 1440; 1440 = no limit), `day` (`all`, the default, `today`, or `sun` … `sat`), or `week` (seven limits, Sunday first, in place of `minutes` and `day`) | Sets a day's limit, every day's, today's only, or the whole week's. |
| `playguard.add_bonus_time` | `minutes` (5 to 180, default 30) | Extra minutes today; the usual limit comes back tomorrow. |
| `playguard.apply_profile` | `profile` (its name in PlayGuard) | Applies the limits of a saved profile. |
| `playguard.stop_today` | | 0 minutes today; the usual limit comes back tomorrow. |
| `playguard.lock_now` | | Turns parental controls back on after a temporary unlock. |
| `playguard.sync_now` | | The console publishes everything again. |
| `playguard.request_report` | | The console saves a diagnostic report on its SD card, and publishes it when *Remote access* allows it (then in the device's diagnostics). |
| `playguard.get_play_time` | `period` (`today`, the default, or `week`) | Returns the play time as the action's response (*Response variable* in a script): today's (`minutes`, `games` with each one's `app_id`, `name`, `minutes`, `accounts`, `now_playing`, `limit_minutes`, `remaining_minutes`, `extra_minutes`, `blocked`, `blocked_by`, `bedtime`, `parental_controls`), or the last seven days' (`days`, `minutes`, `games` with each one's `per_day`, `accounts`). Sends nothing to the console. |

```yaml
actions:
  - action: playguard.get_play_time
    data:
      device_id: 0123456789abcdef0123456789abcdef
      period: week
    response_variable: week
  - action: notify.notify
    data:
      message: "{{ week.minutes }} minutes this week, {{ week.games[0].name }} first."
```

`set_limits`, `add_bonus_time`, `apply_profile` and `stop_today` need
*Orders may change the play timer*.

## 🔔 Events

The *Events* entity fires once per order the console handled, and once per
thing the console does on its own (sent by its agent, in a PlayGuard that has
them), with one of these event types:

| Event type | When |
|---|---|
| `command_applied` | The order was carried out. |
| `command_rejected` | The order was refused; `reason` says why (`policy_off`, `timer_writes_disabled`, `read_only`, `not_confirmed`, `out_of_range`, `no_such_profile` …, see PlayGuard's [protocol](https://github.com/JigSawFr/PlayGuard/blob/main/docs/sync-protocol.md)). |
| `command_waiting` | The order waits for PlayGuard (the agent keeps it until PlayGuard confirms it, under *Ask on the console*). |
| `play_started` | A game started (`game`, `app_id`). |
| `play_stopped` | The game stopped: closed, suspended, or another one started (`play_stopped` comes first). |
| `time_warning` | 10 minutes or fewer left of today's limit while a game is played (`minutes_left`); once, and again after extra time takes it back above 10. |
| `play_blocked` | Games are blocked: `blocked_by` is `limit` (the day's limit, or *No more play today*) or `bedtime`. |

Attributes: `entity` (the order's entity), `payload` (its value), `reason`,
`rc` (the console's result code, `0x…`, when it answered), `source` (`app`
or `agent`), `ts` (when, POSIX time); and for what the console did on its
own, `app_id`, `game` (its name), `minutes_left`, `blocked_by`. The console
builds its state every 30 seconds while a game is played, so these come
within that. Events are not retained: one sent while
Home Assistant was away is not seen; *Last order* keeps the last result.

## 🎯 Triggers and conditions

In the automation editor, *Add trigger* and *Add condition* offer the
console's own, under PlayGuard; their target is the console's device (or its
area, or the entity itself).

| Trigger | When |
|---|---|
| `playguard.game_started` | A game starts. |
| `playguard.game_stopped` | The game stops: closed, suspended, or another one started. |
| `playguard.time_running_out` | 10 minutes or fewer are left of today's limit while a game is played. |
| `playguard.games_blocked` | Games are blocked; `blocked_by`: `limit` (the day's limit, or *No more play today*), `bedtime`, or both (the default). |
| `playguard.order_refused` | The console refuses an order. |

The trigger's `trigger.to_state` is the *Events* entity's state, with the
event's attributes (`game`, `minutes_left`, `reason` …, see [events](#-events)).

| Condition | Passes when |
|---|---|
| `playguard.is_playing` | A game is played (*Now playing* names one). |
| `playguard.limit_reached` | Today's limit is reached. |
| `playguard.parental_controls_on` | Parental controls are on, not unlocked for now. |

```yaml
triggers:
  - trigger: playguard.time_running_out
    target:
      device_id: 0123456789abcdef0123456789abcdef
conditions:
  - condition: playguard.is_playing
    target:
      device_id: 0123456789abcdef0123456789abcdef
    options:
      behavior: any
```

## 💬 Assist and AI assistants

Three intents: `PlayGuardPlayTime` (today's play time, the game played, what
is left of the limit), `PlayGuardAddTime` (`minutes`, 5 to 180: extra time
today) and `PlayGuardStopToday` (no more play today); each takes the
console's `name` when there are several. An assistant that uses Home
Assistant's LLM API (*Assist* in its settings) gets them as tools as soon as
one of the console's entities is exposed to it (*Settings › Voice assistants
› Expose*): "how long did they play today?", "give them 30 more minutes".
They answer in Home Assistant's language. Orders go through the same checks
as the actions, and a refusal is said.

Home Assistant's own Assist (without an LLM) needs the sentences, in
`custom_sentences/en/playguard.yaml` of the configuration folder:

```yaml
language: en
intents:
  PlayGuardPlayTime:
    data:
      - sentences:
          - "how long [did they play|have they played] [on the Switch] [today]"
          - "[how much] time left on the Switch"
  PlayGuardAddTime:
    data:
      - sentences:
          - "(give|add) {minutes} [more] minutes [on the Switch]"
  PlayGuardStopToday:
    data:
      - sentences:
          - "no more [Switch] games today"
lists:
  minutes:
    range:
      from: 5
      to: 180
      step: 5
```

## 🔄 Data updates

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
  the last 14. The **game names** and the **week** table come when PlayGuard
  itself runs (not the agent); *Play time this week* moves on without it, day
  by day, from the play log and the finished days (each account's time too,
  from an agent that reads it).
- **Last seen** is the time of the last document the console published while
  Home Assistant listened (its state comes every `poll_s` seconds while it is
  awake), else, after a restart, the time of its last state.
- **What is published** (the state's `link.publishes`): the entities of what
  PlayGuard stops publishing go at once; those of what it publishes again come
  back with a reload of the entry.
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

## 💡 Examples

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

Time is up: say so on the phone (not at bedtime, which blocks games too).

```yaml
alias: Switch time is up
triggers:
  - trigger: state
    entity_id: binary_sensor.living_room_playing_blocked
    to: "on"
conditions:
  - condition: state
    entity_id: binary_sensor.living_room_playing_blocked
    attribute: reason
    state: limit
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

A family dashboard: today's play time and what is left, the game being
played, extra time in one tap, blocking all games, the last 14 days, and the
games played last (from *Games installed*). Change
`living_room` and `a1b2c3d4` (the console's id, *Settings › Devices &
services › PlayGuard*) to yours:

```yaml
type: vertical-stack
cards:
  - type: tile
    entity: sensor.living_room_play_time_today
  - type: tile
    entity: sensor.living_room_screen_time_remaining
  - type: tile
    entity: sensor.living_room_now_playing
  - type: grid
    columns: 3
    square: false
    cards:
      - type: button
        name: +15 min
        icon: mdi:timer-plus-outline
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.living_room_extra_time_15_min
      - type: button
        name: +30 min
        icon: mdi:timer-plus-outline
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.living_room_extra_time_30_min
      - type: button
        name: +1 h
        icon: mdi:timer-plus-outline
        tap_action:
          action: perform-action
          perform_action: button.press
          target:
            entity_id: button.living_room_extra_time_1_h
  - type: tile
    entity: switch.living_room_block_all_games
  - type: statistics-graph
    entities:
      - playguard:a1b2c3d4_play_time
    period: day
    days_to_show: 14
    stat_types:
      - mean
    chart_type: bar
  - type: markdown
    content: |-
      {%- set games = state_attr('sensor.living_room_games_installed', 'games') or [] -%}
      {%- for g in games[:5] %}
      - **{{ g.name }}** {{ (g.minutes or 0) // 60 }} h {{ '%02d' % ((g.minutes or 0) % 60) }}
      {%- endfor %}
```

## 📘 Blueprints

Ready-made automations: import one, then *Create automation* from it and pick
the console's entities and the phone (the Home Assistant app).

| Blueprint | What it does | Import |
|---|---|---|
| **Time is up, extra time from the notification** | When the day's limit is reached (not at bedtime), a notification on the phone with a button that gives extra time (*+15 min*, or what you set). | [![Import the time is up blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FJigSawFr%2Fplayguard-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplayguard%2Ftime_is_up.yaml) |
| **A few minutes left, extra time from the notification** | When a game has 10 minutes left before the day's limit (the event *Play time almost over*), a notification on the phone with the game, the minutes left and a button that gives extra time. | [![Import the time warning blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FJigSawFr%2Fplayguard-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplayguard%2Ftime_warning.yaml) |
| **Extra time when…** | Extra time when something happens: a helper turned on (the chores done), a button or a remote pressed, a tag scanned; then what you like (turn the helper off again). | [![Import the extra time blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FJigSawFr%2Fplayguard-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplayguard%2Fextra_time.yaml) |
| **Bedtime reminder** | A notification some minutes before *Bedtime alarm*, while a game is played (or every day). | [![Import the bedtime reminder blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FJigSawFr%2Fplayguard-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplayguard%2Fbedtime_reminder.yaml) |
| **Still playing after bedtime** | When a game is played between *Bedtime* and *Wake-up time*: bedtime came with a game on, or one started in the night. For when the play timer is off, or the alarm only warns. | [![Import the still playing after bedtime blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FJigSawFr%2Fplayguard-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplayguard%2Fafter_bedtime.yaml) |
| **Evening summary** | Today's play time at a set time: the total, each child's (when the console read the accounts) and the games played the most; nothing on a day without play. | [![Import the evening summary blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FJigSawFr%2Fplayguard-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplayguard%2Fevening_summary.yaml) |
| **Weekly summary** | Once a week, the last seven days' play time and the games played the most. | [![Import the weekly summary blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FJigSawFr%2Fplayguard-ha%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fplayguard%2Fweekly_summary.yaml) |

The ones that give extra time need *Orders may change the play timer* on the
console. Their notifications are in English: change the text in the
automation, or the blueprint's copy in `blueprints/automation/playguard/`.

## 🏡 Use cases

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

## 🚧 Known limitations

- PlayGuard runs on a console with custom firmware (Atmosphère); there is
  none for the Nintendo Switch 2.
- Some things are never possible from Home Assistant, by PlayGuard's design:
  reading, setting or changing the PIN, deleting parental controls, unlinking
  the phone app.
- While the console is offline, a control shows its last value until the
  console wakes up and carries out what was changed (the order waits on the
  broker). Under *Ask
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
  last 14) once the integration was set up. Each account's come from
  PlayGuard's week (its last 7 days, PlayGuard itself must have run): a week
  without PlayGuard leaves a gap.
- The entity ids may differ from those of the console's own MQTT device.

## 🩺 Troubleshooting

<details>
<summary>No PlayGuard console in <em>Discovered</em></summary>

The console publishes nothing on the broker Home Assistant uses, or under
another prefix. On the console, *Console › Remote access › Status* must
read *Online* (PlayGuard open, or its agent running), with the same broker as
Home Assistant's MQTT integration. A prefix other than `playguard` is never
discovered: add the console by hand, where it is listed (a prefix of one or
two levels) or added by its id.
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
other than *Refuse them*, in PlayGuard › *Console › Remote access*.
Read-only mode means a firmware PlayGuard does not support yet: update
PlayGuard.
</details>

<details>
<summary>An order is sent but nothing happens</summary>

Under *Ask on the console*, PlayGuard asks on the console before carrying it
out (event `command_waiting` when the agent keeps it). A sleeping console
carries it out when it wakes up. *Last order* and the *Events* entity say
what became of it; a refusal then raises a notification.
</details>

<details>
<summary>Repair: "… publishes its own Home Assistant device again"</summary>

The console's own MQTT device is back next to this integration's, so every
entity is there twice. The repair asks the console again to turn it off. If
it comes back, update PlayGuard, or turn off *Create the device in Home
Assistant (MQTT discovery)* in PlayGuard › *Console › Remote access*. To
keep the console's own device instead, turn off the option *Replace the
console's own Home Assistant device*.
</details>

<details>
<summary>Repair: "… runs an older PlayGuard agent"</summary>

PlayGuard was updated on the console, but its agent was not: the offer to
update it at start-up was put off. Update it in PlayGuard › *Console ›
Optional modules › Link agent*. The repair goes once both versions match.
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
the statistic `playguard:<console id>_play_time` (or a game's, or an
account's) in a
*Statistics graph* card.
</details>

For anything else, download the diagnostics (*Settings › Devices & services
› PlayGuard › ⋮ › Download diagnostics*: the console's last documents and
report, names left out) and open an
[issue](https://github.com/JigSawFr/playguard-ha/issues).

## 🧹 Removal

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

## 📡 What it does on the broker

It reads `playguard/<id>/state`, `system`, `games`, `availability`, `activity`,
`activity/<date>`, `names`, `week`, `event` and `report`, and publishes the
same retained scalar orders as the native entities on
`playguard/<id>/<entity>/set` (the console clears each one once handled), and
its version, retained, on `playguard/<id>/integration`. Adding a console by
hand listens to `+/+/state` and `+/+/+/state` for a few seconds, to list the
consoles there. The contract is PlayGuard's
[`docs/sync-protocol.md`](https://github.com/JigSawFr/PlayGuard/blob/main/docs/sync-protocol.md).

## 🤝 Help, security and contributing

- A problem with the integration: [Getting help](https://github.com/JigSawFr/playguard-ha/blob/main/.github/SUPPORT.md) says
  where to ask; a bug report wants the console's diagnostics (the device's
  page, *⋮ › Download diagnostics*: names and account ids left out).
- A security problem: privately, as [SECURITY.md](https://github.com/JigSawFr/playguard-ha/blob/main/SECURITY.md) says, never in
  a public issue.
- Working on the integration (tests, coverage, the quality scale, the parity
  with PlayGuard's entity table, translations, releases):
  [CONTRIBUTING.md](https://github.com/JigSawFr/playguard-ha/blob/main/CONTRIBUTING.md). Changes are listed in
  [CHANGELOG.md](https://github.com/JigSawFr/playguard-ha/blob/main/CHANGELOG.md).
- Support PlayGuard: [GitHub Sponsors](https://github.com/sponsors/JigSawFr)
  or [Ko-fi](https://ko-fi.com/jigsawfr).

## 📜 License

**GPLv3** (see [`LICENSE`](https://github.com/JigSawFr/playguard-ha/blob/main/LICENSE)), as PlayGuard. Maintained by [JigSawFr](https://github.com/JigSawFr).

<sub>Not affiliated with or endorsed by Nintendo or the Home Assistant project. Nintendo Switch is a trademark of Nintendo.</sub>

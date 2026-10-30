# Security policy

## Reporting a vulnerability

Report privately through GitHub, from the repository's **Security** tab:
[Report a vulnerability](https://github.com/JigSawFr/boreale-ha/security/advisories/new).
That opens a private advisory visible only to you and the maintainer. Please do not open a
public issue: the integration sends orders to a console that guards a child's play time,
and a way around what PlayGuard allows is useful to exactly the people it is meant to hold
back from the moment it is readable.

Expect an acknowledgement within a few days. A confirmed report is fixed in a new release,
and the advisory is published once that release is out.

Include, if you can: the Home Assistant version, the integration's version, the PlayGuard
version on the console, what a person gains, and the smallest sequence of steps that
shows it.

## Supported versions

The latest release. Fixes are not backported.

## What is in scope

- **Orders** — an action, a button, a number, a select, a switch or a time entity sending
  more than the console's own entity table allows (an order that deletes parental controls,
  unlinks the companion app, reads or changes the PIN); an order the integration must
  refuse being sent anyway: the console in read-only mode, its orders turned off, a
  play-timer order while *Orders may change the play timer* is off.
- **Topics** — a console id, a topic prefix or a payload from the broker making the
  integration read or publish outside that console's own topics (`<prefix>/<id>/…`), or
  act on another console's entry.
- **Diagnostics and logs** — the downloaded diagnostics or the log carrying what they
  leave out on purpose: the console's name, the profiles' names, account ids and nicknames,
  the game names; or anything of the broker's (its address, user name or password).
- **Repairs** — the repair flow of *the console's own device is back* asking another
  console than its own, or doing more than turning that console's own discovery off.
- **Messages from the broker** — a malformed or oversized document crashing the
  integration or blocking Home Assistant's event loop.

## What is not

- **Whoever can publish to the broker.** With PlayGuard's remote link on, the broker's
  users are trusted to send orders (that is what the link is for): securing the broker,
  its users and the local network, and keeping *Orders may change the play timer* off on
  the console when it is not needed, is the owner's part. The integration holds no
  credentials of its own; Home Assistant's MQTT integration holds the broker's.
- **PlayGuard itself.** What the console does with an order, the PIN, the agent sysmodule
  and the console's own Home Assistant discovery belong to PlayGuard: report them under
  [its security policy](https://github.com/JigSawFr/PlayGuard/security/policy).
- **Home Assistant.** The recorder, the MQTT integration, users and permissions belong to
  [Home Assistant's security policy](https://www.home-assistant.io/security/).
- **Nintendo's parental controls.** Neither PlayGuard nor this integration is affiliated
  with Nintendo.

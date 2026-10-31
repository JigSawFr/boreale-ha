# Changelog

## [0.10.1](https://github.com/JigSawFr/boreale-ha/compare/v0.10.0...v0.10.1) (2026-10-31)


### 📚 Documentation

* **branding:** rename the README and brand images to Boréale for Home Assistant ([#50](https://github.com/JigSawFr/boreale-ha/issues/50)) ([c3962ee](https://github.com/JigSawFr/boreale-ha/commit/c3962ee19f077cd8d24a5979b4666ca5a2bc8699))

## [0.10.0](https://github.com/JigSawFr/boreale-ha/compare/v0.9.0...v0.10.0) (2026-10-31)


### 🚀 Features

* **sensor:** the Boréale homebrews' notifications, from their shared bell ([#45](https://github.com/JigSawFr/boreale-ha/issues/45)) ([77330be](https://github.com/JigSawFr/boreale-ha/commit/77330be16f4d5c0be174a88befc6ba20977afb55))
* **site:** build on boreale-site, with Boréale's header and a dashboard hero ([#47](https://github.com/JigSawFr/boreale-ha/issues/47)) ([4ba613d](https://github.com/JigSawFr/boreale-ha/commit/4ba613d4d28d166af9fe93b698ce325e2974887c))

## [0.9.0](https://github.com/JigSawFr/boreale-ha/compare/v0.8.0...v0.9.0) (2026-10-30)


### ⚠ BREAKING CHANGES

* **init:** the domain is boreale; automations using the triggers and conditions playguard.* must use boreale.*.

### 🚀 Features

* **activity:** what the console is doing, and the homebrews counted ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **assist:** the play time as an action's response, and intents for Assist and AI assistants ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **automation:** the console's own triggers and conditions in the automation editor ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **coordinator:** follow the console to Boréale's topic tree ([#40](https://github.com/JigSawFr/boreale-ha/issues/40)) ([3392446](https://github.com/JigSawFr/boreale-ha/commit/3392446ceb93fc00eb22236968dd456f5ebb563c))
* **i18n:** German, Spanish, Italian, Japanese, Korean, Dutch, Portuguese, Russian and Chinese ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **image:** the icon of the game being played ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **init:** Boréale for Nintendo Switch, domain boreale, taking over playguard ([#41](https://github.com/JigSawFr/boreale-ha/issues/41)) ([0035a13](https://github.com/JigSawFr/boreale-ha/commit/0035a13044e754df1e0e432786ea2d0613de3b70))
* **native:** the console's answers, triggers and conditions, Assist, update, game icon, activity, 14 languages ([#33](https://github.com/JigSawFr/boreale-ha/issues/33)) ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **orders:** a refused order fails with the console's reason, and a refusal that comes later raises a notification ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **repairs:** the settings that refuse orders as repairs, the console's events in the logbook, the device's diagnostics ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))
* **site:** ha.boreale.dev, the integration's site in fifteen languages ([#43](https://github.com/JigSawFr/boreale-ha/issues/43)) ([a7e5c2b](https://github.com/JigSawFr/boreale-ha/commit/a7e5c2b4832de0f6ffcafadf2dfc5f08e4b71c57))
* **update:** PlayGuard's version against its latest release ([387c4c0](https://github.com/JigSawFr/boreale-ha/commit/387c4c02740aa20e74670fc22be4f549e008a775))


### 🐞 Bug Fixes

* **coordinator:** a document of a newer schema is no longer read ([#38](https://github.com/JigSawFr/boreale-ha/issues/38)) ([cfd748e](https://github.com/JigSawFr/boreale-ha/commit/cfd748e053a25f90348f16ecb3ca9383301edab3))
* **release:** the pre-release found from the release PR's branch ([#36](https://github.com/JigSawFr/boreale-ha/issues/36)) ([9fea093](https://github.com/JigSawFr/boreale-ha/commit/9fea09349e0ffc902dc5fc017c79b788db1f81d4))
* **services:** the playguard.* actions no longer answer, nothing of the old integration kept ([#44](https://github.com/JigSawFr/boreale-ha/issues/44)) ([9231826](https://github.com/JigSawFr/boreale-ha/commit/92318268635762443f11f3fb1d6c217515edaab0))


### 📚 Documentation

* **readme:** the READMEs and CONTRIBUTING caught up with what the integration does ([#37](https://github.com/JigSawFr/boreale-ha/issues/37)) ([ce9c956](https://github.com/JigSawFr/boreale-ha/commit/ce9c9562ce418d1118432728397b5cb67bf5cb55))

## [0.8.0](https://github.com/JigSawFr/playguard-ha/compare/v0.7.0...v0.8.0) (2026-10-26)


### 🚀 Features

* **entities:** Firmware and Atmosphère off by default, as on the console ([#31](https://github.com/JigSawFr/playguard-ha/issues/31)) ([710e65e](https://github.com/JigSawFr/playguard-ha/commit/710e65ee21e119c9b2fa0fcad799fdd500d5692e))

## [0.7.0](https://github.com/JigSawFr/playguard-ha/compare/v0.6.0...v0.7.0) (2026-10-26)


### 🚀 Features

* **accounts:** a play time sensor per account, today and this week ([#28](https://github.com/JigSawFr/playguard-ha/issues/28)) ([073b51e](https://github.com/JigSawFr/playguard-ha/commit/073b51e09927893b491d452e6c4ae18a5002e98d))
* **blueprints:** still playing after bedtime, and an evening summary ([#30](https://github.com/JigSawFr/playguard-ha/issues/30)) ([b79557f](https://github.com/JigSawFr/playguard-ha/commit/b79557f673441e1af4c22930826723a7b4a98712))
* **calendar:** the play sessions as a calendar ([#29](https://github.com/JigSawFr/playguard-ha/issues/29)) ([723dd39](https://github.com/JigSawFr/playguard-ha/commit/723dd39326a4ef6fa3fe8b5396b36262422b7bdf))
* **device:** a 10-minute warning blueprint, a repair for an older agent, truer agent and play ends ([#26](https://github.com/JigSawFr/playguard-ha/issues/26)) ([9274447](https://github.com/JigSawFr/playguard-ha/commit/927444744cd4f48d0a3625f0b84b2b8f2c924b98))


### 🐞 Bug Fixes

* **availability:** keep the controls while the console sleeps ([#24](https://github.com/JigSawFr/playguard-ha/issues/24)) ([61d3a68](https://github.com/JigSawFr/playguard-ha/commit/61d3a6814e688c14d8618bdabeeba21682546dd2))
* **week:** count today's play since PlayGuard last wrote the week ([#23](https://github.com/JigSawFr/playguard-ha/issues/23)) ([008274a](https://github.com/JigSawFr/playguard-ha/commit/008274a8a64a067ef54962547728da8ff6846697))
* **week:** move the week on from the agent's play log and finished days, accounts included ([#27](https://github.com/JigSawFr/playguard-ha/issues/27)) ([824ac5b](https://github.com/JigSawFr/playguard-ha/commit/824ac5b1b7c1c198adc07f1db7b6ce00e5332765))

## [0.6.0](https://github.com/JigSawFr/playguard-ha/compare/v0.5.0...v0.6.0) (2026-10-26)


### 🚀 Features

* **brand:** Aurore's aurora, a house for an icon, and a README with screenshots ([#22](https://github.com/JigSawFr/playguard-ha/issues/22)) ([4ccdb3e](https://github.com/JigSawFr/playguard-ha/commit/4ccdb3e3197227438e8c5d0cc8135228866a2a0c))
* **events:** a game started or stopped, 10 minutes left, games blocked ([#21](https://github.com/JigSawFr/playguard-ha/issues/21)) ([2c160ef](https://github.com/JigSawFr/playguard-ha/commit/2c160ef4fe3746ccf942484d5d6d83d49daf428f))
* **sensors:** each account's play time, and when play ends ([#19](https://github.com/JigSawFr/playguard-ha/issues/19)) ([3500ba6](https://github.com/JigSawFr/playguard-ha/commit/3500ba6e013696854bbec97bc478add511d12148))


### 📚 Documentation

* **readme:** links that work in HACS, how to get an update at once, the profile in effect ([#18](https://github.com/JigSawFr/playguard-ha/issues/18)) ([d40f3df](https://github.com/JigSawFr/playguard-ha/commit/d40f3df203f30f9565b7c45417be954ec7eadd9d))

## [0.5.0](https://github.com/JigSawFr/playguard-ha/compare/v0.4.0...v0.5.0) (2026-10-26)


### ⚠ BREAKING CHANGES

* **entities:** Unlocked, Turn parental controls back on and Temporarily unlocked are gone, replaced by the lock Parental controls; Time is up is named Playing blocked (its entity id stays); Used screen time and each day's limit are disabled by default for new entries.

### 🚀 Features

* **entities:** the console as Nintendo names it, a lock for parental controls, what PlayGuard publishes, platinum ([#16](https://github.com/JigSawFr/playguard-ha/issues/16)) ([a6ad3fe](https://github.com/JigSawFr/playguard-ha/commit/a6ad3fec8ed914345eaba7406c5bfc78ef60f4a0))

## [0.4.0](https://github.com/JigSawFr/playguard-ha/compare/v0.3.0...v0.4.0) (2026-10-25)


### ⚠ BREAKING CHANGES

* **entities:** the sensors "Play time · <game>" and the option "Game sensors" are removed; an automation on one of them reads the games attribute instead.

### ⚠️ Changes

* **entities:** no sensor per game, every game stays on one entity ([#14](https://github.com/JigSawFr/playguard-ha/issues/14)) ([3830d8f](https://github.com/JigSawFr/playguard-ha/commit/3830d8f27c5d457ea013e040580b2859f01319db))

## [0.3.0](https://github.com/JigSawFr/playguard-ha/compare/v0.2.0...v0.3.0) (2026-10-25)


### 🚀 Features

* **blueprints:** time is up with extra time from the notification, extra time on any trigger, a bedtime reminder, a weekly summary ([72465eb](https://github.com/JigSawFr/playguard-ha/commit/72465eb262a8c66416b09fe94ee0290616fe9de4))
* **config-flow:** adding a console by hand lists the consoles found on the broker ([72465eb](https://github.com/JigSawFr/playguard-ha/commit/72465eb262a8c66416b09fe94ee0290616fe9de4))
* **entities:** a sensor only for the games played lately (an option: none, recent, every game), and every game listed on Games installed ([72465eb](https://github.com/JigSawFr/playguard-ha/commit/72465eb262a8c66416b09fe94ee0290616fe9de4))
* **entities:** the sensors keep their last values while the console sleeps ([#11](https://github.com/JigSawFr/playguard-ha/issues/11)) ([f087913](https://github.com/JigSawFr/playguard-ha/commit/f0879136da7b8b93f59305176619dc61e2a85819))
* **entities:** what few dashboards need is off by default, as in PlayGuard's own discovery ([72465eb](https://github.com/JigSawFr/playguard-ha/commit/72465eb262a8c66416b09fe94ee0290616fe9de4))


### 📚 Documentation

* **readme:** a family dashboard example ([72465eb](https://github.com/JigSawFr/playguard-ha/commit/72465eb262a8c66416b09fe94ee0290616fe9de4))

## [0.2.0](https://github.com/JigSawFr/playguard-ha/compare/v0.1.0...v0.2.0) (2026-10-25)


### 🚀 Features

* **entities:** the console's information and one sensor per game ([#3](https://github.com/JigSawFr/playguard-ha/issues/3)) ([8263a4e](https://github.com/JigSawFr/playguard-ha/commit/8263a4efd7ecc1e2959565f530015a3b56a4f969))

## 0.1.0 (2026-10-25)


### 🚀 Features

* **integration:** the PlayGuard integration — consoles found on the broker, entities, statistics, services ([#1](https://github.com/JigSawFr/playguard-ha/issues/1)) ([1a206d8](https://github.com/JigSawFr/playguard-ha/commit/1a206d8447479e534bc57122dc802ba2b24aca5f))

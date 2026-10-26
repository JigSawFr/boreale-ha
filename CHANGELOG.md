# Changelog

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

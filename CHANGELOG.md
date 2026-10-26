# Changelog

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

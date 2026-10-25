# PlayGuard pour Home Assistant

[![validate](https://github.com/JigSawFr/playguard-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/JigSawFr/playguard-ha/actions/workflows/validate.yml)
[![latest release](https://img.shields.io/github/v/release/JigSawFr/playguard-ha)](https://github.com/JigSawFr/playguard-ha/releases/latest)
[![HACS: custom](https://img.shields.io/badge/HACS-custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![quality scale: gold](https://img.shields.io/badge/quality%20scale-gold-d4af37.svg)](custom_components/playguard/quality_scale.yaml)
[![license: GPLv3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)

[English](README.md) · **Français**

[![Ouvrez votre instance Home Assistant et ouvrez un dépôt dans le Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=JigSawFr&repository=playguard-ha&category=integration)
[![Ouvrez votre instance Home Assistant et commencez à configurer une nouvelle intégration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=playguard)

Une intégration Home Assistant pour [PlayGuard](https://github.com/JigSawFr/PlayGuard),
le homebrew Nintendo Switch qui gère le contrôle parental de la console hors
ligne : limites de temps de jeu, heure du coucher, restrictions, temps en plus,
verrou de console. PlayGuard publie l'état de la console, son temps de jeu et
ses événements sur un broker MQTT de votre réseau local, et reçoit des ordres
par lui (*Préférences › Accès à distance*, et son agent facultatif qui garde le
lien quand PlayGuard est fermé). Cette intégration fait de chaque console un
appareil Home Assistant : voir le temps restant, changer les limites, donner du
temps en plus, bloquer tous les jeux, depuis un tableau de bord ou une
automatisation.

La console fonctionne avec Home Assistant **sans** cette intégration : elle
publie elle-même la découverte MQTT de Home Assistant. L'intégration ajoute :

- **Trouvée toute seule** : chaque console qui publie sur le broker est
  proposée à la configuration, sans identifiant à saisir.
- **Les mêmes entités** que l'appareil MQTT d'origine de la console (noms,
  unités, options), à sa place (pas de doublons ; réactivez-le dans les
  options), plus **En ligne**, **Agent actif** et **Temps de jeu cette semaine**.
- **Les noms des jeux** sur *Jeu en cours*, et le temps de chaque jeu
  aujourd'hui et cette semaine en attributs.
- **Des statistiques à long terme** : le total de chaque journée terminée, et
  celui de chaque jeu, importés dans l'enregistreur (`playguard:<console id>_play_time`,
  `playguard:<console id>_game_<application id>`), pour des mois d'historique
  dans une carte *Graphique des statistiques*.
- **Des ordres pendant que la console est en veille** : ses entités sont alors
  indisponibles (son message de testament dit qu'elle est partie), mais les
  actions envoient quand même leurs ordres, qui attendent sur le broker et sont
  exécutés quand la console sort de veille.
- **Des actions** : `set_limits`, `add_bonus_time`, `apply_profile`,
  `stop_today`, `lock_now`, `sync_now`, `request_report`.
- Une **entité d'événement** pour chaque ordre traité (exécuté, refusé avec la
  raison, en attente de la confirmation de PlayGuard), pour les automatisations.
- Un ordre que la console refuserait (mode lecture seule, ordres refusés,
  écriture du minuteur non autorisée) est refusé ici, avec la raison.
- Des **réparations** quand vous devez agir, et des **diagnostics** avec le
  dernier état de la console et son dernier rapport de diagnostic, sans les noms.

**Sommaire** : [appareils pris en charge](#appareils-pris-en-charge) ·
[prérequis](#prérequis) · [installation](#installation) ·
[configuration](#configuration) · [options et reconfiguration](#options-et-reconfiguration) ·
[entités](#entités) · [actions](#actions) · [événements](#événements) ·
[mise à jour des données](#mise-à-jour-des-données) · [exemples](#exemples) ·
[cas d'usage](#cas-dusage) · [limites connues](#limites-connues) ·
[dépannage](#dépannage) · [désinstallation](#désinstallation) ·
[aide, sécurité et contribution](#aide-sécurité-et-contribution)

## Appareils pris en charge

- Les consoles **Nintendo Switch** (le modèle d'origine, le modèle OLED, la
  Lite) sous Atmosphère, avec un PlayGuard qui a *Préférences › Accès à
  distance*. Ce que PlayGuard lui-même prend en charge est sur sa page
  [compatibilité](https://github.com/JigSawFr/PlayGuard/blob/main/docs/fr/compatibility.md) :
  testé sur les firmwares 22.0.0 à 22.5.0 (Atmosphère 1.11.x) ; sur un firmware
  plus récent, il s'ouvre en lecture seule, et chaque ordre est refusé jusqu'à
  ce qu'une version de PlayGuard le prenne en charge ; avant le firmware 21.0.0,
  il n'a pas de minuteur (limites, heure du coucher, temps en plus, verrou de
  console).
- La **sysMMC et l'emuMMC** d'une console sont deux appareils : chacune a son
  propre contrôle parental et son propre identifiant de console.
- **Non pris en charge** : la Nintendo Switch 2 (Atmosphère n'existe pas pour
  elle), et une console sans PlayGuard. Pour l'application et le compte
  Contrôle parental de Nintendo, voyez plutôt l'intégration *Nintendo Switch
  Parental Controls* de Home Assistant.
- **Home Assistant 2026.10 ou plus récent**, et un broker MQTT en version 5.0
  ou 3.1.1 : l'application Mosquitto, ou EMQX, HiveMQ, NanoMQ,
  VerneMQ et d'autres. La console parle 5.0 et se replie sur 3.1.1.
  L'intégration MQTT de Home Assistant passe d'elle-même à 5.0 quand le broker
  l'accepte, sinon elle signale une réparation, *Échec de la migration du
  protocole MQTT* (Home Assistant abandonne 3.1.1 avec la 2027.1).

## Prérequis

1. Un broker MQTT, et l'intégration **MQTT** de Home Assistant configurée
   dessus (*Paramètres › Appareils et services › Ajouter une intégration ›
   MQTT* ; avec l'application Mosquitto, elle est proposée d'elle-même).
2. Un utilisateur du broker pour la console (avec l'application Mosquitto, tout
   utilisateur de Home Assistant peut se connecter : créez-en un nommé `playguard`).
3. Sur la console, le lien de PlayGuard configuré sur ce broker : *Préférences ›
   Accès à distance › MQTT / Home Assistant* (adresse du broker, port, nom
   d'utilisateur et mot de passe, nom dans Home Assistant), puis *Lien à
   distance* activé. Son *État* affiche *En ligne*. Le
   [guide Home Assistant](https://github.com/JigSawFr/PlayGuard/blob/main/docs/home-assistant.fr.md)
   de PlayGuard donne les détails, et l'agent facultatif qui garde le lien quand
   PlayGuard est fermé.
4. Pour changer les limites, l'heure du coucher ou le temps en plus depuis Home
   Assistant : *Les ordres peuvent changer le temps de jeu* activé, dans le même
   écran. *Ordres reçus* dit si la console demande avant d'exécuter un ordre
   (par défaut), l'exécute aussitôt, ou le refuse.

## Installation

Avec [HACS](https://hacs.xyz/) :

1. *HACS › ⋮ › Dépôts personnalisés* : ajoutez
   `https://github.com/JigSawFr/playguard-ha`, type *Intégration* ; ou le
   premier bouton en haut de cette page (My Home Assistant ouvre le dépôt dans
   votre HACS). Dans PlayGuard, *Accès à distance › Home Assistant ›
   Installer l'intégration Home Assistant* affiche les deux mêmes boutons en
   QR codes, pour un téléphone.
2. Ouvrez **PlayGuard** dans HACS, puis *Télécharger* : HACS installe le
   `playguard.zip` de la version que vous choisissez.
3. Redémarrez Home Assistant.

À la main : téléchargez `playguard.zip` depuis la
[dernière version](https://github.com/JigSawFr/playguard-ha/releases/latest),
extrayez-le dans un dossier `custom_components/playguard` de votre
configuration, et redémarrez Home Assistant. Le zip de chaque version porte une
attestation de provenance de build : `gh attestation verify playguard.zip -R JigSawFr/playguard-ha`
vérifie qu'il a été construit par la CI de ce dépôt (`SHA256SUMS.txt`, à côté,
donne sa somme de contrôle).

## Configuration

**Trouvée sur le broker.** Chaque console qui publie (PlayGuard ouvert, ou son
agent actif) apparaît dans *Paramètres › Appareils et services › Découvertes* :

1. Sélectionnez **PlayGuard** sous *Découvertes*.
2. Confirmez la console (son nom et son identifiant sont affichés). Rien à saisir.

**À la main** (une console qui n'est pas trouvée, ou un préfixe autre que
`playguard`) :

1. *Paramètres › Appareils et services › Ajouter une intégration › PlayGuard*.
2. Remplissez les champs ci-dessous, puis *Valider*. L'intégration attend
   jusqu'à 10 secondes l'état de la console sur le broker, et crée l'entrée avec
   le nom de la console ; s'il n'y a rien, elle le dit et vous laisse corriger
   les champs.

| Champ | Quoi mettre |
|---|---|
| **Identifiant de la console** | Les 8 caractères de la console (0 à 9, a à f), dans PlayGuard › *Préférences › Accès à distance › Identifiant de la console*. |
| **Préfixe des topics** | `playguard`, sauf si `topic_prefix` dans le `sync.conf` de la console dit autre chose. |

Chaque console est une entrée et un appareil ; la même console ne peut pas être
ajoutée deux fois.

## Options et reconfiguration

*Paramètres › Appareils et services › PlayGuard › ⚙ (Configurer)* :

| Option | Par défaut | Ce qu'elle fait |
|---|---|---|
| **Remplacer l'appareil Home Assistant d'origine de la console** | activée | Désactive la découverte MQTT de la console, pour que ses entités n'apparaissent pas deux fois. Désactivée : la console publie de nouveau son propre appareil (à côté de celui-ci). L'entrée se recharge quand elle change. |

*⋮ › Reconfigurer* change le **Préfixe des topics**, quand `topic_prefix` dans
le `sync.conf` de la console change. Comme pour l'ajout d'une console à la main,
la console doit répondre sous le nouveau préfixe ; l'entrée se recharge alors.

Une console revenue au préfixe `playguard` est de nouveau trouvée par la
découverte, et son entrée la suit (et se recharge) dès que la console publie un
état plus récent que le dernier lu par l'entrée ; un état resté sur le broker
sous l'ancien préfixe ne la fait pas revenir en arrière.

## Entités

Un appareil par console, au nom de la console (*Nom dans Home Assistant* dans
PlayGuard), avec son firmware et la version de PlayGuard. Les entités de
*configuration* et de *diagnostic* sont dans leurs propres sections de la page
de l'appareil et hors des tableaux de bord par défaut. Toutes sont indisponibles
tant que la console est hors ligne, sauf *En ligne*.

**Capteurs binaires**

| Entité | Ce qu'elle indique | Remarques |
|---|---|---|
| Contrôle parental | Le contrôle parental est configuré sur la console. | |
| Déverrouillé temporairement | Le contrôle parental est déverrouillé pour l'instant (le code PIN a été saisi). | classe d'appareil *Serrure* : *Déverrouillé* quand il est actif |
| Application mobile liée | L'application mobile de Nintendo est liée à la console. | |
| Minuteur de jeu | La limite quotidienne de temps de jeu est activée. | |
| Temps écoulé | La limite du jour est atteinte. | |
| Code PIN défini | Un code PIN est défini. | diagnostic |
| Horloge réseau exacte | L'horloge de la console est réglée depuis le réseau. | diagnostic |
| En ligne | La console est sur le broker en ce moment (sinon : en veille, éteinte, hors de portée). | diagnostic, propre à cette intégration |
| Agent actif | L'agent de PlayGuard garde le lien. | diagnostic, désactivé par défaut, propre à cette intégration |

**Capteurs** (minutes)

| Entité | Ce qu'elle indique | Remarques |
|---|---|---|
| Temps d'écran utilisé | Le temps de jeu du jour, tel que le minuteur le compte. | total quotidien, remis à 0 à minuit |
| Temps d'écran utilisé (journal de jeu) | Le temps de jeu du jour d'après le journal de jeu, avec les minutes de chaque jeu (`games`). | total quotidien |
| Temps d'écran restant | Ce qui reste de la limite du jour. | |
| Temps d'écran prolongé | Le temps en plus accordé aujourd'hui. | |
| Temps de jeu cette semaine | Les 7 derniers jours, avec les minutes de chaque jour (`days`) et de chaque jeu (`games`). | propre à cette intégration ; une fois que PlayGuard lui-même a tourné |
| Jeu en cours | Le jeu en cours, par son nom (attributs `app_id`, `since`). | inconnu tant que PlayGuard est ouvert (personne ne joue alors) |
| Âge de classification | L'âge de classification du niveau de restriction. | diagnostic |
| Firmware, Atmosphère | Les versions de la console. | diagnostic |
| Dernier ordre | Le dernier ordre traité, et comment. | diagnostic |
| Temps passé (1952) | Le décompte brut du minuteur. | diagnostic, désactivé par défaut |

**Nombres** (configuration, minutes, 0 à 1440 ; 1440 signifie pas de limite) :
*Limite dimanche* … *Limite samedi*, *Limite tous les jours* (inconnue quand les
jours diffèrent), *Temps d'écran max aujourd'hui* (aujourd'hui seulement ; la
limite habituelle revient demain).

**Heure** (configuration) : *Alarme du coucher* (quand l'alarme sonne), *Fin du
coucher* (quand le jeu est de nouveau permis).

**Interrupteurs** : *Bloquer tous les jeux* (plus de jeu du tout),
*Déverrouillé* (désactivé, il réactive le contrôle parental après un
déverrouillage temporaire) ; configuration : *Alarme du coucher activée*,
*Alarme de fin de temps*, *Mode VR restreint*, *Publication sur les réseaux
sociaux restreinte*, *Communication restreinte*.

**Sélecteurs** (configuration) : *Niveau de restriction* (sans restriction,
jeune enfant, enfant, adolescent, personnalisé), *Profil* (applique l'un des
profils enregistrés dans PlayGuard ; il n'affiche aucun choix en cours : les
limites disent lequel s'applique).

**Boutons** : *Temps en plus +15 min*, *+30 min*, *+1 h*, *Fin du jeu pour
aujourd'hui*, *Retirer la limite*, *Réactiver le contrôle parental* (après un
déverrouillage temporaire) ; diagnostic : *Synchroniser maintenant* (la console republie
tout), *Exporter un rapport de diagnostic*.

**Événement** : *Événements*, voir [événements](#événements).

**La console elle-même** (`playguard/<id>/system`, tenu à jour par l'agent
quand PlayGuard est fermé) :

| Entité | Ce qu'elle indique | Notes |
|---|---|---|
| Batterie, En charge, Sur le dock | Sa charge, si un chargeur l'alimente, si elle est sur le dock. | |
| Espace libre de la carte SD, Espace libre du stockage interne | Mio restants sur la carte SD et sur le stockage utilisateur du système (celui de l'emuMMC sur un emuMMC). | lus toutes les 5 minutes ; leurs tailles sont de diagnostic |
| Modèle | Switch (2017), Switch (2019), Switch Lite, Switch OLED. | diagnostic |
| Surnom de la console, Région, Système, hekate | Le surnom des Paramètres de la console, la région, sysMMC ou emuMMC, hekate sur la carte SD. | diagnostic |
| PRODINFO masqué | Atmosphère cache l'identité de la console. | diagnostic |
| Température, Connexion, Adresse IP, Signal Wi-Fi | Le capteur interne, Wi-Fi ou ethernet, l'adresse de la console, 0 à 3 barres. | diagnostic |
| Dernier démarrage | Quand la console a démarré (pas quand elle est sortie de veille). | diagnostic |
| Numéro de série | Le vrai numéro de série de la console (tiré de la sauvegarde d'Atmosphère quand le PRODINFO est masqué). | diagnostic, désactivé par défaut ; seulement avec *Publier le numéro de série* sur la console |
| Réseau Wi-Fi | Le nom du réseau. | diagnostic, désactivé par défaut |

**Jeux** (`playguard/<id>/games`, que PlayGuard publie après chaque lecture
du journal de jeu) : *Jeux installés*, *Temps de jeu (depuis toujours)* (tous
les jeux, tous les comptes), *Comptes utilisateurs* (diagnostic) ; et **un
capteur par jeu**, *Temps de jeu · <jeu>* : ses minutes depuis sa première
partie (un total croissant, pour les statistiques à long terme), avec les
attributs `installed`, `version`, `launches`, `first_played`, `last_played`.
Le capteur d'un jeu apparaît quand la console le liste pour la première fois,
et reste quand le jeu est désinstallé (avec `installed: false`) ; celui d'un
jeu que la console ne liste plus est indisponible.

Les entités qui changent le minuteur (limites, heure du coucher, temps en plus,
blocage de tous les jeux, profils) demandent *Les ordres peuvent changer le
temps de jeu* activé sur la console ; sans lui, elles sont refusées ici avec la
raison. Réactiver le contrôle parental (*Déverrouillé* désactivé) et les restrictions n'en ont
pas besoin.

Home Assistant construit lui-même les identifiants d'entités, à partir des noms
de l'appareil et des entités, lors de leur premier enregistrement, et vous
pouvez les changer : ils peuvent différer de ceux de l'appareil MQTT d'origine
de la console, vérifiez donc les automatisations qui utilisaient ceux-là.

## Actions

Chaque action prend l'**appareil** de la console (`device_id`), et envoie un
ordre retenu : quand la console est en veille, il attend sur le broker et est
exécuté quand elle sort de veille. Un ordre que la console refuserait est refusé
aussitôt, avec la raison (mode lecture seule, ordres refusés, écriture du
minuteur désactivée, profil inconnu, appareil qui n'est pas une console
PlayGuard chargée).

| Action | Champs | Ce qu'elle fait |
|---|---|---|
| `playguard.set_limits` | `minutes` (0 à 1440 ; 1440 = pas de limite), `day` (`all`, par défaut, `today`, ou `sun` … `sat`), ou `week` (sept limites, dimanche d'abord, à la place de `minutes` et `day`) | Règle la limite d'un jour, de tous les jours, d'aujourd'hui seulement, ou de toute la semaine. |
| `playguard.add_bonus_time` | `minutes` (5 à 180, 30 par défaut) | Des minutes en plus aujourd'hui ; la limite habituelle revient demain. |
| `playguard.apply_profile` | `profile` (son nom dans PlayGuard) | Applique les limites d'un profil enregistré. |
| `playguard.stop_today` | | 0 minute aujourd'hui ; la limite habituelle revient demain. |
| `playguard.lock_now` | | Réactive le contrôle parental après un déverrouillage temporaire. |
| `playguard.sync_now` | | La console republie tout. |
| `playguard.request_report` | | La console enregistre un rapport de diagnostic sur sa carte SD, et le publie quand *Accès à distance* le permet (il est alors dans les diagnostics de l'appareil). |

`set_limits`, `add_bonus_time`, `apply_profile` et `stop_today` demandent
*Les ordres peuvent changer le temps de jeu*.

## Événements

L'entité *Événements* se déclenche une fois par ordre traité par la console,
avec l'un de ces types d'événements :

| Type d'événement | Quand |
|---|---|
| `command_applied` | L'ordre a été exécuté. |
| `command_rejected` | L'ordre a été refusé ; `reason` dit pourquoi (`policy_off`, `timer_writes_disabled`, `read_only`, `not_confirmed`, `out_of_range`, `no_such_profile`…, voir le [protocole](https://github.com/JigSawFr/PlayGuard/blob/main/docs/sync-protocol.md) de PlayGuard, en anglais). |
| `command_waiting` | L'ordre attend PlayGuard (l'agent le garde jusqu'à ce que PlayGuard le confirme, avec *Demander sur la console*). |

Attributs : `entity` (l'entité de l'ordre), `payload` (sa valeur), `reason`,
`rc` (le code de résultat de la console, `0x…`, quand elle a répondu), `source`
(`app` ou `agent`), `ts` (quand, en temps POSIX). Les événements ne sont pas
retenus : un événement envoyé pendant que Home Assistant était absent n'est pas
vu ; *Dernier ordre* garde le dernier résultat.

## Mise à jour des données

Rien n'est interrogé : la console pousse par MQTT, et Home Assistant ne fait
qu'écouter.

- La console publie son **état** quand il change, et toutes les `poll_s`
  secondes pour un horodatage frais (30 par défaut, de 10 à 300, dans son
  `sync.conf`). Quand PlayGuard est fermé, l'agent lit la console toutes les
  `poll_s` secondes.
- Tout sauf les événements est **retenu** sur le broker : après un redémarrage
  de Home Assistant, les derniers documents arrivent aussitôt, même d'une
  console en veille.
- La **disponibilité** est le message de testament de la console : une console
  qui se met en veille ou quitte le réseau est marquée hors ligne en
  45 secondes environ (keep-alive de 30 s). L'intégration le journalise une
  fois quand elle part, une fois quand elle revient.
- Le **journal de jeu** du jour (`activity`) arrive avec l'état ; une journée
  terminée (`activity/<date>`) au premier cycle après minuit, la console
  gardant les 14 dernières. Les **noms des jeux** et la **semaine** arrivent
  quand PlayGuard lui-même tourne (pas l'agent).
- **Statistiques** : les journées terminées sont importées 5 secondes après
  l'arrivée de la dernière (elles arrivent en rafale) ; importer de nouveau une
  journée la remplace.
- Les **ordres** sont retenus jusqu'à ce que la console les traite ; elle les
  efface alors, publie un événement et son nouvel état.
- **La version de l'intégration** : à chaque configuration de l'entrée d'une
  console (donc à chaque démarrage de Home Assistant), l'intégration publie
  sa version et celle de Home Assistant, retenues, sur
  `playguard/<id>/integration`. PlayGuard l'affiche dans *Accès à distance ›
  Home Assistant* et, quand il cherche les mises à jour, signale dans ses
  notifications qu'une nouvelle version de l'intégration est sortie, avec ce
  qui change et le QR code qui l'ouvre dans HACS.

## Exemples

Les identifiants d'entités dépendent du nom de la console (ici *Living room*) :
vérifiez-les sur la page de l'appareil. L'appareil des actions se choisit dans
l'interface ; en YAML, c'est l'identifiant de l'appareil (sur la page de
l'appareil, *⋮ › Informations sur l'appareil*, ou dans l'URL).

Une notification quand un ordre est refusé :

```yaml
alias: Ordre PlayGuard refusé
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
        PlayGuard a refusé {{ trigger.to_state.attributes.entity }} :
        {{ trigger.to_state.attributes.reason }}
```

Le temps est écoulé : le dire sur le téléphone.

```yaml
alias: Temps de Switch écoulé
triggers:
  - trigger: state
    entity_id: binary_sensor.living_room_time_is_up
    to: "on"
actions:
  - action: notify.notify
    data:
      message: "Plus de Switch aujourd'hui : la limite est atteinte."
```

Les limites des vacances depuis un calendrier, celles de la semaine scolaire
ensuite :

```yaml
alias: Limites des vacances
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
      profile: "{{ 'Vacances' if trigger.event == 'start' else 'Semaine scolaire' }}"
```

Du temps en plus pour les tâches faites :

```yaml
alias: Tâches faites, 30 minutes de plus
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

Un bouton de tableau de bord pour 30 minutes de plus :

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

## Cas d'usage

- Voir d'un coup d'œil combien de temps les enfants ont joué aujourd'hui et ce
  qui reste, sur le tableau de bord familial ou un téléphone.
- Donner du temps en plus, arrêter le jeu pour aujourd'hui ou bloquer tous
  les jeux depuis le canapé ou le travail, sans prendre la console ni le code PIN.
- Passer d'un profil semaine scolaire à un profil vacances depuis un calendrier,
  ou régler les limites du week-end le vendredi soir.
- Récompenser les tâches ménagères ou les devoirs par du temps en plus, avec un
  bouton ou une entrée.
- Être prévenu quand le temps est écoulé, quand un ordre est refusé, ou quand la
  console est restée allumée après l'heure du coucher.
- Garder des mois d'historique de jeu, par jour et par jeu, dans une carte
  *Graphique des statistiques*, longtemps après que la console les a oubliés.

## Limites connues

- PlayGuard tourne sur une console sous firmware personnalisé (Atmosphère) ; il
  n'y en a pas pour la Nintendo Switch 2.
- Certaines choses ne sont jamais possibles depuis Home Assistant, par
  conception de PlayGuard : lire, définir ou changer le code PIN, supprimer le
  contrôle parental, dissocier l'application mobile.
- Tant que la console est hors ligne, ses entités sont indisponibles : seules
  les actions peuvent alors envoyer des ordres, et ceux-ci attendent la console.
  Avec *Demander sur la console*, un ordre attend aussi que quelqu'un le
  confirme sur la console (événement `command_waiting`) ; avec *Les refuser*,
  rien n'est appliqué.
- Sans *Les ordres peuvent changer le temps de jeu*, les limites, l'heure du
  coucher, le temps en plus, le blocage de tous les jeux et les profils sont
  refusés (l'appareil d'origine de la console masque plutôt ces entités).
- Seul le préfixe `playguard` est découvert ; une console sous un autre préfixe
  s'ajoute à la main.
- *Jeu en cours* est inconnu tant que PlayGuard est ouvert (et renseigné par
  l'agent sinon) ; la semaine et les noms des jeux demandent que PlayGuard
  lui-même ait tourné.
- Les statistiques n'ont que les journées terminées que la console gardait
  encore (les 14 dernières) au moment où l'intégration a été configurée.
- Les identifiants d'entités peuvent différer de ceux de l'appareil MQTT
  d'origine de la console.
- *Profil* n'a pas de choix en cours : la console ne dit pas quel profil
  s'applique.

## Dépannage

<details>
<summary>Aucune console PlayGuard dans <em>Découvertes</em></summary>

La console ne publie rien sur le broker qu'utilise Home Assistant, ou publie
sous un autre préfixe. Sur la console, *Préférences › Accès à distance › État*
doit afficher *En ligne* (PlayGuard ouvert, ou son agent actif), avec le même
broker que l'intégration MQTT de Home Assistant. Un préfixe autre que
`playguard` n'est jamais découvert : ajoutez la console à la main.
</details>

<details>
<summary>« Cette console n'a rien publié sur le broker sous ce préfixe. »</summary>

Lors d'un ajout à la main ou d'une reconfiguration, aucun état n'est venu de cet
identifiant de console sous ce préfixe. Vérifiez l'identifiant (*Accès à
distance › Identifiant de la console* : celui de l'emuMMC diffère de celui de la
sysMMC), le préfixe (`topic_prefix` dans `sync.conf`), et que le lien de la
console a été en ligne au moins une fois sur ce broker.
</details>

<details>
<summary>« L'intégration MQTT n'est pas encore configurée »</summary>

PlayGuard parle à Home Assistant par l'intégration MQTT : configurez-la
d'abord, sur le même broker que la console, puis ajoutez PlayGuard.
</details>

<details>
<summary>Toutes les entités sont indisponibles</summary>

La console est hors ligne (*En ligne* est désactivé) : en veille, éteinte, hors
du Wi-Fi, ou PlayGuard fermé sans son agent. Les entités reviennent quand elle
est de nouveau en ligne. Les ordres envoyés par les actions entre-temps
attendent sur le broker.
</details>

<details>
<summary>« Les ordres ne peuvent pas changer le temps de jeu… » / « La console refuse les ordres… » / « PlayGuard est en mode lecture seule sur cette console… »</summary>

La console refuserait l'ordre, donc Home Assistant ne l'envoie pas. Activez
*Les ordres peuvent changer le temps de jeu*, ou réglez *Ordres reçus* sur autre
chose que *Les refuser*, dans PlayGuard › *Préférences › Accès à distance*.
Le mode lecture seule signifie un firmware que PlayGuard ne prend pas encore en
charge : mettez PlayGuard à jour.
</details>

<details>
<summary>Un ordre est envoyé mais rien ne se passe</summary>

Avec *Demander sur la console*, PlayGuard demande sur la console avant de
l'exécuter (événement `command_waiting` quand l'agent le garde). Une console en
veille l'exécute quand elle sort de veille. *Dernier ordre* et l'entité
*Événements* disent ce qu'il est devenu.
</details>

<details>
<summary>Réparation : « … publie de nouveau son propre appareil Home Assistant »</summary>

L'appareil MQTT d'origine de la console est revenu à côté de celui de cette
intégration, donc chaque entité apparaît deux fois. La réparation demande de
nouveau à la console de le désactiver. S'il revient, mettez PlayGuard à jour, ou
désactivez *Créer l'appareil dans Home Assistant (découverte MQTT)* dans
PlayGuard › *Préférences › Accès à distance*. Pour garder plutôt l'appareil
d'origine de la console, désactivez l'option *Remplacer l'appareil Home
Assistant d'origine de la console*.
</details>

<details>
<summary>Réparation : « … parle un protocole PlayGuard plus récent »</summary>

Le PlayGuard de la console est plus récent que cette intégration : mettez à jour
l'intégration PlayGuard (HACS). D'ici là, certaines valeurs peuvent manquer.
</details>

<details>
<summary>Le graphique des statistiques est vide</summary>

Les statistiques demandent l'enregistreur (actif par défaut), et ne contiennent
que les journées terminées : la première apparaît après le premier cycle de la
console passé minuit. Choisissez la statistique `playguard:<console id>_play_time`
(ou celle d'un jeu) dans une carte *Graphique des statistiques*.
</details>

Pour tout le reste, téléchargez les diagnostics (*Paramètres › Appareils et
services › PlayGuard › ⋮ › Télécharger les diagnostics* : les derniers documents
et le dernier rapport de la console, sans les noms) et ouvrez un
[ticket](https://github.com/JigSawFr/playguard-ha/issues).

## Désinstallation

1. *Paramètres › Appareils et services › PlayGuard*, puis pour chaque console
   *⋮ › Supprimer*. Supprimer l'entrée d'une console demande à la console de
   publier de nouveau son propre appareil Home Assistant (une console en veille
   le fait quand elle sort de veille), et efface la version de l'intégration
   sur le broker (PlayGuard ne signale plus ses nouvelles versions) ; pour vous
   passer de l'appareil de la console, désactivez *Créer l'appareil dans Home
   Assistant* dans PlayGuard.
2. Avec HACS : *HACS › PlayGuard › ⋮ › Désinstaller* ; à la main : supprimez
   `custom_components/playguard`. Redémarrez Home Assistant.
3. Les statistiques à long terme restent dans l'enregistreur : supprimez-les
   dans *Paramètres › Outils › Statistiques* si vous n'en voulez plus.

Rien d'autre ne reste sur le broker : la console efface chaque ordre une fois
traité. Pour que la console arrête complètement de publier, désactivez *Lien à
distance* dans PlayGuard.

## Ce qu'elle fait sur le broker

Elle lit `playguard/<id>/state`, `system`, `games`, `availability`, `activity`,
`activity/<date>`, `names`, `week`, `event` et `report`, et publie les mêmes
ordres scalaires retenus que les entités natives sur
`playguard/<id>/<entity>/set` (la console efface chacun une fois traité), et
sa version, retenue, sur `playguard/<id>/integration`. Le contrat est le
[`docs/sync-protocol.md`](https://github.com/JigSawFr/PlayGuard/blob/main/docs/sync-protocol.md)
de PlayGuard (en anglais).

## Aide, sécurité et contribution

- Un problème avec l'intégration : [Obtenir de l'aide](.github/SUPPORT.md) (en
  anglais) dit où demander ; un rapport de bug demande les diagnostics de la
  console (la page de l'appareil, *⋮ › Télécharger les diagnostics* : sans les
  noms ni les identifiants de compte).
- Un problème de sécurité : en privé, comme le dit [SECURITY.md](SECURITY.md)
  (en anglais), jamais dans un ticket public.
- Travailler sur l'intégration (tests, couverture, échelle de qualité, parité
  avec la table des entités de PlayGuard, traductions, versions) :
  [CONTRIBUTING.md](CONTRIBUTING.md) (en anglais). Les changements sont listés
  dans [CHANGELOG.md](CHANGELOG.md).
- Soutenir PlayGuard : [GitHub Sponsors](https://github.com/sponsors/JigSawFr)
  ou [Ko-fi](https://ko-fi.com/jigsawfr).

## Licence

GPLv3 (voir [`LICENSE`](LICENSE)), comme PlayGuard.

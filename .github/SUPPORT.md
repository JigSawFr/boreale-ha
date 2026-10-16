# Getting help

The integration has one maintainer, PlayGuard's, and no support channel outside GitHub.
Pick the place that fits, and you will get an answer sooner.

| You want to… | Go to |
|---|---|
| Set up a console, or solve a common problem | The README's [set-up](../README.md#set-up) and [troubleshooting](../README.md#troubleshooting) first |
| Report something the integration gets wrong (an entity, an action, a repair, the statistics) | A [bug report](https://github.com/JigSawFr/playguard-ha/issues/new?template=1-bug.yml), with the console's diagnostics (its device page, *⋮ › Download diagnostics*) |
| Report something the console does with an order, or PlayGuard's own Home Assistant device | A [PlayGuard bug report](https://github.com/JigSawFr/PlayGuard/issues/new?template=1-bug.yml), with PlayGuard's diagnostic report |
| Ask how to do something, or talk an idea through | PlayGuard's [Discussions](https://github.com/JigSawFr/PlayGuard/discussions) |
| Ask for something the integration cannot do yet | A [feature request](https://github.com/JigSawFr/playguard-ha/issues/new?template=2-feature.yml) |
| Report a way around what PlayGuard allows, or another security problem | **Privately**, as the [security policy](../SECURITY.md) says. Never in a public issue |

Never post the broker's password, a full `sync.conf` or the console's PIN in an issue or a
discussion. The integration's diagnostics leave out the console's name, the profiles,
account ids and game names on purpose; a debug log may not: read it before you attach it.

Neither PlayGuard nor this integration is affiliated with Nintendo. Questions about the
phone app or a Nintendo account belong with Nintendo support, and Home Assistant's own
*Nintendo Switch Parental Controls* integration is a different one.

# The website

<https://ha.boreale.dev/>: what Boréale for Nintendo Switch does, how to
install it and the move from the PlayGuard integration, in the consoles'
fifteen languages, as Boréale's other sites: English at the root, each other
one in its folder (`/fr/`, `/fr-ca/`, `/de/` … `/zh-hant/`).

It is made the way boreale.dev is (`JigSawFr/boreale`, its `site/README.md`,
the reference): the same look, aurora and fonts (`assets/site.css`,
`assets/site.js`, `assets/fonts/`), the same menu of Boréale's sites in the
header (`SITES` in `tools/build_site.py`, this site under *Integrations*),
the same language menu (`assets/lang.js`), the same rules for links out (no
referrer; `utm_source=ha` on the links to our other sites only), the same
Content-Security-Policy and the same audience count (Umami Cloud, without
cookie, from `ha.boreale.dev` only: `assets/umami.js`). A change to one of
these shared parts is made in boreale.dev first, then copied here.

## How it is made

`python3 tools/build_site.py <out-dir>` (Python 3, nothing to install):

- `template.html`: the page around the content; `hero.html` and `home.html`:
  the home page (features, the three install steps, the move from PlayGuard);
  `legal.html`: `legal/`, the privacy and legal notice, written in French
  (each other language says it is a translation); `lost.html`: `404.html`.
- `i18n/<language>.json`: each `{{key}}`'s text. The keys the sites share
  (the menu of Boréale's sites, the legal notice's common parts) are
  boreale.dev's word for word.
- The integration's latest version, under the hero's buttons and in the
  menu, comes from GitHub's API; the other projects' from boreale.dev's
  `versions.json`. `SITE_OFFLINE=1` builds without them; `GITHUB_TOKEN`
  lifts the API's anonymous limit; `SITE_URL` is the site's address.
- `assets/`: the icons (`favicon.svg` is `branding/icon.svg`; the PNGs and
  `favicon.ico` rendered from it), the social preview
  (`.github/readme/social-preview.png`), the marks of Boréale's sites.
- No contact address: the contact is the repository's issues, a security
  flaw its private advisories (`.well-known/security.txt`).

## Checks

- `python3 tools/check_site.py <site>`: the catalogs have the same keys, no
  `{{key}}` is left, every link and anchor leads somewhere, the links out
  follow the rules, nothing the Content-Security-Policy blocks is on a page.
- `tools/site_layout.py <site>` (Playwright for Python): every page on phones,
  a tablet and a desktop, and axe-core against WCAG 2.2 AA
  (`SITE_AXE=<axe.min.js>`).

## Publishing

`.github/workflows/site.yml` builds and checks the site for each pull request
and for main, publishes main's on GitHub Pages, and builds again once a day
(published only when it differs from the site served, by `build.sha256`).

Once, in the repository's settings: *Pages › Build and deployment › Source:
GitHub Actions*, then *Custom domain: ha.boreale.dev* and *Enforce HTTPS*.
The `ha` record at the registrar is a `CNAME` to `jigsawfr.github.io`.

# The website

<https://ha.boreale.dev/>: what Boréale for Nintendo Switch does, how to
install it and the move from the PlayGuard integration, in the consoles'
fifteen languages, as Boréale's other sites: English at the root, each other
one in its folder (`/fr/`, `/fr-ca/`, `/de/` … `/zh-hant/`).

What Boréale's sites share is `library/boreale-site`, a submodule
(`JigSawFr/boreale-site`, its README): the languages, the brand's colours and
fonts (`boreale.css`), the menu of Boréale's sites in the header (this site
under *Integrations*) and the language menu (`boreale.js`, `lang.js`), the
marks, the rules for links out (no referrer; `utm_source=ha` on the links to
our other sites only), the Content-Security-Policy's checks and the audience
count (Umami Cloud, without cookie, from `ha.boreale.dev` only: `umami.js`).
A change to one of them is made there; Dependabot then moves the submodule
here. After a clone: `git submodule update --init`.

## How it is made

`python3 tools/build_site.py <out-dir>` (Python 3, nothing to install):

- `template.html`: the page around the content, its header in PlayGuard's
  site's way (guard.boreale.dev, the reference for the look): the site's
  wordmark, *Boréale for HA*, opening the menu of Boréale's sites, the links,
  *Open in HACS* lit, GitHub and the languages; on two rows on a phone.
  `hero.html` and `home.html`: the home page, its hero (the text, and a
  console's card on a Home Assistant dashboard drawn beside it, `.panel` in
  `site.css`, its texts `mock_*` and fictional names), then the features,
  the three install steps, the move from PlayGuard and the promise;
  `legal.html`: `legal/`, the privacy and legal notice, written in French
  (each other language says it is a translation); `lost.html`: `404.html`.
- `i18n/<language>.json`: each `{{key}}`'s text, English in `en-US.json`.
  The texts every site has (the menu of Boréale's sites, the language
  button) are boreale-site's, never repeated here: the build stops if one
  is.
- The integration's latest release, over the hero's title (its version and
  date, leading to its notes) and in the menu, comes from GitHub's API; the other projects' from boreale.dev's
  `versions.json`. `SITE_OFFLINE=1` builds without them; `GITHUB_TOKEN`
  lifts the API's anonymous limit; `SITE_URL` is the site's address.
- `assets/`: this site's own, `site.css` and `site.js` (the aurora, the
  sections), the icons (`favicon.svg` is `branding/icon.svg`; the PNGs and
  `favicon.ico` rendered from it) and the social preview
  (`.github/readme/social-preview.png`). boreale-site's assets are copied
  beside them at the build; one of them here too stops it.
- No contact address: the contact is the repository's issues, a security
  flaw its private advisories (`.well-known/security.txt`).

## Checks

- `python3 tools/check_site.py <site>`: boreale-site's checks
  (`boreale_site.check`: no `{{key}}` left, every link and anchor leads
  somewhere, the links out follow the rules, nothing the
  Content-Security-Policy blocks, the tracker on every page, no e-mail
  address) and its catalogs' (the same keys as `en-US.json`, none empty),
  then this site's own (`sitemap.xml`, the manifest's icons).
- `library/boreale-site/tools/site_layout.py <site>` (Playwright for
  Python): every page on phones, a tablet and a desktop, and axe-core against
  WCAG 2.2 AA (`SITE_AXE=<axe.min.js>`).

## Publishing

`.github/workflows/site.yml` builds and checks the site for each pull request
and for main, publishes main's on GitHub Pages, and builds again once a day
(published only when it differs from the site served, by `build.sha256`).

Once, in the repository's settings: *Pages › Build and deployment › Source:
GitHub Actions*, then *Custom domain: ha.boreale.dev* and *Enforce HTTPS*.
The `ha` record at the registrar is a `CNAME` to `jigsawfr.github.io`.

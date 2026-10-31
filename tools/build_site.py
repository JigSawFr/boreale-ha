#!/usr/bin/env python3
"""Builds ha.boreale.dev, the site of Boréale for Home Assistant, into
<out-dir> (site/README.md).

    python3 tools/build_site.py <out-dir>

site/template.html is the page around site/hero.html and site/home.html (the
home page), site/legal.html (legal/: privacy and legal notice) or
site/lost.html (404.html); each {{key}} is the key's text in the language's
catalog, site/i18n/<language>.json, or in boreale-site's. The consoles'
fifteen languages, as Boréale's other sites have them: English at the root,
each other one in its folder (fr/, fr-ca/, de/ ... zh-hant/). The languages,
the header's menus, the rules for links out, the audience and the shared
assets are boreale-site's (library/boreale-site, a submodule).

The integration's latest release comes from GitHub's API, the other
projects' from boreale.dev's versions.json, at each build: GITHUB_TOKEN,
when set, lifts the API's rate limit; SITE_OFFLINE=1 builds without them.
SITE_URL is the site's address (https://ha.boreale.dev/ by default).
build.sha256 is a hash of everything built.
"""
import html
import json
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
# What Boréale's sites share (library/boreale-site, a submodule): the
# languages, the header's menus, the links out and their UTM tags, the
# common texts and assets.
sys.path.insert(0, str(ROOT / "library" / "boreale-site"))
import boreale_site as boreale  # noqa: E402
from boreale_site import CODES, OG_LOCALES, attribute, fill, folder, html_lang  # noqa: E402

HA = boreale.Site("ha", os.environ.get("SITE_URL"))
SITE_URL = HA.url
# The language the legal texts are written in, the others translating it
# (legal_translation, said on the other languages' legal page).
ORIGINAL = "fr"
OWNER = "JigSawFr"
REPO = "boreale-ha"
# The documentation (the README, in French for French readers) and
# PlayGuard's guide to its side of the link, on GitHub.
DOCS = {"en": f"https://github.com/{OWNER}/{REPO}#readme", "fr": f"https://github.com/{OWNER}/{REPO}/blob/main/README.fr.md"}
GUIDE = {"en": f"https://github.com/{OWNER}/PlayGuard/blob/main/docs/home-assistant.md",
         "fr": f"https://github.com/{OWNER}/PlayGuard/blob/main/docs/home-assistant.fr.md"}
# My Home Assistant's link that opens this repository in the visitor's HACS.
HACS = (f"https://my.home-assistant.io/redirect/hacs_repository/?owner={OWNER}&amp;repository={REPO}"
        "&amp;category=integration")

# The pages other than 404.html, by their path under each language's folder.
PAGES = {"": "home.html", "legal/": "legal.html"}


def fetch(url: str) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "boreale-ha-site"}
    if os.environ.get("GITHUB_TOKEN") and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as answer:
        return json.load(answer)


def versions() -> tuple:
    """The projects' latest versions, for the menu of Boréale's sites: the
    others' from boreale.dev's versions.json (boreale-site), this one's from
    GitHub; and this one's latest release (version, date, address) for the
    hero, or None (none offline, or when they cannot be read: the site builds
    without them)."""
    latest = boreale.latest_versions()
    if os.environ.get("SITE_OFFLINE") == "1":
        return latest, None
    try:
        release = fetch(f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest")
        version = release["tag_name"].lstrip("v")
        published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00")).date()
    except Exception as error:
        print(f"build_site: the latest release not read ({error})", file=sys.stderr)
        return latest, None
    latest[HA.key] = version
    return latest, (version, published, release["html_url"])


def release_pill(release: tuple, language: str) -> str:
    """The latest release and its date over the hero's title (chrome.css's
    .pill-eyebrow), leading to its notes; nothing without one."""
    if not release:
        return ""
    version, published, url = release
    return (f'<p class="pill-eyebrow"><a href="{attribute(url)}">v{html.escape(version)} · '
            f'<time datetime="{published.isoformat()}">{boreale.day(published, language)}</time></a></p>')


def structured(language: str, catalog: dict, latest: dict) -> str:
    """schema.org data for search engines: the integration, by Boréale."""
    item = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Boréale for Home Assistant",
            "url": HA.address(language), "description": catalog["description"], "inLanguage": html_lang(language),
            "applicationCategory": "HomeAutomationApplication", "operatingSystem": "Home Assistant",
            "license": "https://www.gnu.org/licenses/gpl-3.0.html",
            "sameAs": f"https://github.com/{OWNER}/{REPO}",
            "publisher": {"@type": "Organization", "name": "Boréale", "url": "https://boreale.dev/"}}
    if HA.key in latest:
        item["softwareVersion"] = latest[HA.key]
    text = json.dumps(item, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def header(language: str, catalog: dict, root: str, path: str, latest: dict) -> str:
    """The header: the site's own wordmark, Boréale for HA, with its mark
    (PlayGuard's Play<b>Guard</b>), opening the menu of Boréale's sites; the
    page's links, the way into HACS as its call to action, GitHub."""
    home = root + folder(language)
    french = language.startswith("fr")
    return HA.header(
        language, catalog, root, path,
        links=[("nav_features", f"{home}#features"), ("nav_install", f"{home}#install"),
               ("nav_docs", DOCS["fr" if french else "en"])],
        cta=("cta_hacs", HACS), github=f"https://github.com/{OWNER}/{REPO}", label=catalog["nav_label"], latest=latest,
        brand=f'<img src="{root}assets/marks/{HA.key}.svg" alt="" width="34" height="34"><span>Boréale <b>for HA</b></span>')


def footer(language: str, catalog: dict, root: str) -> str:
    """The footer: Boréale's sites and the support are the library's; this
    site's own column is its repository, its issues and its legal page."""
    home = root + folder(language)
    github = f"https://github.com/{OWNER}/{REPO}"
    return HA.footer(
        language, catalog, root,
        columns=[("Boréale for HA", [("GitHub", github), (catalog["footer_issues"], f"{github}/issues"),
                                     (catalog["footer_legal"], f"{home}legal/")])],
        brand=f'<img src="{root}assets/marks/{HA.key}.svg" alt="" width="20" height="20"> <strong>Boréale for Home Assistant</strong>',
        about=[catalog["footer_made"]], fine=catalog["footer_ha"])


def page(language: str, catalog: dict, hero: str, body: str, root: str, url: str, title: str,
         latest: dict, release: tuple, path: str = "", first_visit: bool = False, lost: bool = False) -> str:
    values = dict(catalog)
    values["description"] = attribute(catalog["description"])
    title = attribute(title)
    french = language.startswith("fr")
    values["docs"] = DOCS["fr" if french else "en"]
    values["guide"] = GUIDE["fr" if french else "en"]
    values["hacs"] = HACS
    values["release"] = release_pill(release, language)
    # The hero's dashboard: its durations as the language writes them.
    def minutes(n: int) -> str:
        return catalog["mock_min"].replace("{n}", str(n))

    def hours(n: int) -> str:
        return catalog["mock_hour"].replace("{n}", str(n))

    values.update(mock_left_value=minutes(25), mock_played_value=minutes(95), mock_limit_value=hours(2),
                  mock_extra_15=minutes(15), mock_extra_30=minutes(30), mock_extra_60=hours(1))
    values["legal_translation"] = ("" if language == ORIGINAL else
                                   f'<p class="translation">{catalog["legal_translation"]}</p>')
    values["lang"] = html_lang(language)
    values["home"] = folder(language)
    values["og_locale"] = OG_LOCALES[language]
    # The root's home page sends a first visit to the browser's language
    # (boreale-site's lang.js), and 404.html at the root a visitor reading
    # another language to that language's.
    values["first_visit"] = " data-first-visit" if first_visit else ""
    values["lost"] = f' data-lost="{root}"' if lost and language == CODES[0] else ""
    values["indexing"] = HA.indexing(language, path, lost)
    # The page's chrome (boreale-site's chrome.css and chrome.js): the skip
    # link, the sky (the aurora behind the home page's hero and the page not
    # found, which has no veils under it; a quieter one elsewhere), the
    # header and the footer.
    values["skip"] = HA.skip(catalog)
    values["sky"] = HA.sky(home=bool(hero) or lost, veils=not lost)
    # The header's languages: this page in each (none for 404.html, which
    # is at any address).
    values["header"] = header(language, catalog, root, path if not lost else "", latest)
    values["footer"] = footer(language, catalog, root)
    values["og_alternates"] = "\n".join(
        f'<meta property="og:locale:alternate" content="{OG_LOCALES[code]}">' for code in CODES if code != language)
    values.update(root=root, site=SITE_URL, url=url, title=title)
    values["audience"] = HA.audience(root)
    values["jsonld"] = structured(language, catalog, latest)
    values["hero"] = fill(hero, values)
    values["body"] = fill(body, values)
    return HA.links_out(fill((SITE / "template.html").read_text(encoding="utf-8"), values))


def manifest(catalog: dict) -> str:
    return json.dumps({
        "name": "Boréale for Home Assistant", "short_name": "Boréale HA", "description": catalog["description"],
        "start_url": "/", "display": "browser", "background_color": "#0b1424", "theme_color": "#0b1424",
        "icons": [{"src": "assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}],
    }, ensure_ascii=False, indent=2) + "\n"


def security(now: datetime) -> str:
    """.well-known/security.txt (RFC 9116): where to report a flaw privately.
    It expires a year after the month it was built in, so that a daily build
    changes it only once a month."""
    expires = now.replace(year=now.year + 1, month=now.month, day=1, hour=0, minute=0, second=0, microsecond=0)
    return (f"Contact: https://github.com/{OWNER}/{REPO}/security/advisories/new\n"
            f"Expires: {expires.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            "Preferred-Languages: en, fr\n"
            f"Canonical: {SITE_URL}.well-known/security.txt\n")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    latest, release = versions()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SITE / "assets", out / "assets")
    # boreale-site's: the fonts, the marks, Umami's tracker, lang.js,
    # boreale.css and boreale.js.
    boreale.copy_assets(out)

    hero = (SITE / "hero.html").read_text(encoding="utf-8")
    bodies = {path: (SITE / name).read_text(encoding="utf-8") for path, name in PAGES.items()}
    lost = (SITE / "lost.html").read_text(encoding="utf-8")
    base = urlparse(SITE_URL).path  # 404.html is served at any depth
    catalogs = boreale.catalogs(SITE / "i18n")
    for lang, catalog in catalogs.items():
        for path, body in bodies.items():
            where = folder(lang) + path
            root = "../" * where.count("/")
            home = not path
            (out / where).mkdir(parents=True, exist_ok=True)
            (out / where / "index.html").write_text(
                page(lang, catalog, hero if home else "", body, root, SITE_URL + where,
                     catalog["title"] if home else catalog[f"{path.strip('/')}_page_title"], latest, release, path=path,
                     first_visit=home and lang == CODES[0]),
                encoding="utf-8")
        (out / folder(lang) / "404.html").write_text(
            page(lang, catalog, "", lost, base, SITE_URL, catalog["lost_page_title"], latest, release, lost=True),
            encoding="utf-8")
    first = catalogs[CODES[0]]
    (out / "manifest.webmanifest").write_text(manifest(first), encoding="utf-8")
    shutil.copy(SITE / "assets" / "favicon.ico", out / "favicon.ico")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    (out / ".well-known").mkdir()
    (out / ".well-known" / "security.txt").write_text(security(datetime.now(timezone.utc)), encoding="utf-8")
    (out / "sitemap.xml").write_text(HA.sitemap(PAGES), encoding="utf-8")
    (out / ".nojekyll").touch()
    (out / "build.sha256").write_text(boreale.digest(out) + "\n", encoding="utf-8")
    print(f"build_site: {len(CODES)} languages in {out} for {SITE_URL}")


if __name__ == "__main__":
    main()

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


def versions() -> dict:
    """The projects' latest versions, for the menu of Boréale's sites: the
    others' from boreale.dev's versions.json (boreale-site), this one's from
    GitHub (none offline, or when they cannot be read: the site builds
    without them)."""
    latest = boreale.latest_versions()
    if os.environ.get("SITE_OFFLINE") == "1":
        return latest
    try:
        release = fetch(f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest")
        latest[HA.key] = release["tag_name"].lstrip("v")
    except Exception as error:
        print(f"build_site: the latest release not read ({error})", file=sys.stderr)
    return latest


def structured(language: str, catalog: dict, latest: dict) -> str:
    """schema.org data for search engines: the integration, by Boréale."""
    item = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Boréale for Nintendo Switch",
            "url": HA.address(language), "description": catalog["description"], "inLanguage": html_lang(language),
            "applicationCategory": "HomeAutomationApplication", "operatingSystem": "Home Assistant",
            "license": "https://www.gnu.org/licenses/gpl-3.0.html",
            "sameAs": f"https://github.com/{OWNER}/{REPO}",
            "publisher": {"@type": "Organization", "name": "Boréale", "url": "https://boreale.dev/"}}
    if HA.key in latest:
        item["softwareVersion"] = latest[HA.key]
    text = json.dumps(item, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def page(language: str, catalog: dict, hero: str, body: str, root: str, url: str, title: str,
         latest: dict, path: str = "", first_visit: bool = False, lost: bool = False) -> str:
    values = dict(catalog)
    values["description"] = attribute(catalog["description"])
    title = attribute(title)
    french = language.startswith("fr")
    values["docs"] = DOCS["fr" if french else "en"]
    values["guide"] = GUIDE["fr" if french else "en"]
    values["hacs"] = HACS
    values["boreale_url"] = "https://boreale.dev/" + folder(language)
    values["playguard_url"] = "https://guard.boreale.dev/" + folder(language)
    values["version"] = (catalog["hero_version"].replace("{version}", html.escape(latest[HA.key]))
                         if HA.key in latest else "")
    values["legal_translation"] = ("" if language == ORIGINAL else
                                   f'<p class="translation">{catalog["legal_translation"]}</p>')
    values["lang"] = html_lang(language)
    values["home"] = folder(language)
    values["og_locale"] = OG_LOCALES[language]
    # The header's languages: this page in each (none for 404.html, which
    # is at any address).
    values["languages"] = HA.languages(language, catalog, root, path if not lost else "")
    # The root's home page sends a first visit to the browser's language
    # (boreale-site's lang.js), and 404.html at the root a visitor reading
    # another language to that language's.
    values["first_visit"] = " data-first-visit" if first_visit else ""
    values["lost"] = f' data-lost="{root}"' if lost and language == CODES[0] else ""
    values["indexing"] = HA.indexing(language, path, lost)
    values["page_class"] = ' class="home"' if hero else ""
    values["og_alternates"] = "\n".join(
        f'<meta property="og:locale:alternate" content="{OG_LOCALES[code]}">' for code in CODES if code != language)
    values.update(root=root, site=SITE_URL, url=url, title=title)
    values["switcher"] = HA.switcher(language, catalog, root, latest)
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
    latest = versions()
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
                     catalog["title"] if home else catalog[f"{path.strip('/')}_page_title"], latest, path=path,
                     first_visit=home and lang == CODES[0]),
                encoding="utf-8")
        (out / folder(lang) / "404.html").write_text(
            page(lang, catalog, "", lost, base, SITE_URL, catalog["lost_page_title"], latest, lost=True),
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

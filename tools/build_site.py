#!/usr/bin/env python3
"""Builds ha.boreale.dev, the site of Boréale for Home Assistant, into
<out-dir> (site/README.md).

    python3 tools/build_site.py <out-dir>

site/template.html is the page around site/hero.html and site/home.html (the
home page), site/legal.html (legal/: privacy and legal notice) or
site/lost.html (404.html); each {{key}} is the key's text in the language's
catalog, site/i18n/<language>.json. The consoles' fifteen languages, as
Boréale's other sites have them: English at the root, each other one in its
folder (fr/, fr-ca/, de/ ... zh-hant/). The look, the header's menu of
Boréale's sites and the language menu are boreale.dev's (its site/ and
tools/build_site.py, the reference).

The integration's latest release comes from GitHub's API, the other
projects' from boreale.dev's versions.json, at each build: GITHUB_TOKEN,
when set, lifts the API's rate limit; SITE_OFFLINE=1 builds without them.
SITE_URL is the site's address (https://ha.boreale.dev/ by default).
build.sha256 is a hash of everything built.
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SITE_URL = os.environ.get("SITE_URL", "https://ha.boreale.dev/").rstrip("/") + "/"
# The consoles' languages: the catalog's code (site/i18n/<code>.json), the
# site's folder ('' for the root, the first one), the name in its own words,
# the html lang.
LANGUAGES = [
    ("en", "", "English", "en"),
    ("fr", "fr", "Français", "fr"),
    ("fr-CA", "fr-ca", "Français (Canada)", "fr-CA"),
    ("de", "de", "Deutsch", "de"),
    ("es", "es", "Español", "es"),
    ("es-419", "es-419", "Español (Latinoamérica)", "es-419"),
    ("it", "it", "Italiano", "it"),
    ("nl", "nl", "Nederlands", "nl"),
    ("pt", "pt", "Português", "pt-PT"),
    ("pt-BR", "pt-br", "Português (Brasil)", "pt-BR"),
    ("ru", "ru", "Русский", "ru"),
    ("ja", "ja", "日本語", "ja"),
    ("ko", "ko", "한국어", "ko"),
    ("zh-Hans", "zh-hans", "简体中文", "zh-Hans"),
    ("zh-Hant", "zh-hant", "繁體中文", "zh-Hant"),
]
CODES = [code for code, _, _, _ in LANGUAGES]
# The language the legal texts are written in, the others translating it
# (legal_translation, said on the other languages' legal page).
ORIGINAL = "fr"
# Each language's flag in the language menu (fonts/twemoji-flags.woff2 draws
# them the same everywhere, Windows included): the country of the console's
# language, Mexico for Latin America's Spanish, Taiwan for Traditional Chinese.
FLAGS = {"en": "US", "fr": "FR", "fr-CA": "CA", "de": "DE", "es": "ES", "es-419": "MX", "it": "IT", "nl": "NL",
         "pt": "PT", "pt-BR": "BR", "ru": "RU", "ja": "JP", "ko": "KR", "zh-Hans": "CN", "zh-Hant": "TW"}
# Open Graph's name of each language.
OG_LOCALES = {"en": "en_US", "fr": "fr_FR", "fr-CA": "fr_CA", "de": "de_DE", "es": "es_ES", "es-419": "es_LA",
              "it": "it_IT", "nl": "nl_NL", "pt": "pt_PT", "pt-BR": "pt_BR", "ru": "ru_RU", "ja": "ja_JP",
              "ko": "ko_KR", "zh-Hans": "zh_CN", "zh-Hant": "zh_TW"}
OWNER = "JigSawFr"
REPO = "boreale-ha"
VERSIONS_URL = "https://boreale.dev/versions.json"
# The documentation (the README, in French for French readers) and
# PlayGuard's guide to its side of the link, on GitHub.
DOCS = {"en": f"https://github.com/{OWNER}/{REPO}#readme", "fr": f"https://github.com/{OWNER}/{REPO}/blob/main/README.fr.md"}
GUIDE = {"en": f"https://github.com/{OWNER}/PlayGuard/blob/main/docs/home-assistant.md",
         "fr": f"https://github.com/{OWNER}/PlayGuard/blob/main/docs/home-assistant.fr.md"}
# My Home Assistant's link that opens this repository in the visitor's HACS.
HACS = (f"https://my.home-assistant.io/redirect/hacs_repository/?owner={OWNER}&amp;repository={REPO}"
        "&amp;category=integration")


# Links out say nothing of the visit (workbench rule "liens sortants
# anonymes"): the page sends no referrer (template.html's meta), a link to a
# third party carries rel="noreferrer"; a link to *.boreale.dev or to
# github.com/JigSawFr keeps the origin alone (referrerpolicy="strict-origin"),
# so GitHub's traffic insights still see our sites.
LINK_OUT = re.compile(r'<a\b[^<>]*?\bhref="(https?://[^"]*)"[^<>]*>')


def own_site(url: str) -> bool:
    """boreale.dev, its subdomains, and the repositories of github.com/JigSawFr/
    (that account's alone: another owner, a gist or GitHub's own pages are
    third parties)."""
    u = urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and (host == "boreale.dev" or host.endswith(".boreale.dev") or
                                    (host == "github.com" and u.path.lower().startswith("/jigsawfr/")))

def link_out(tag: str, url: str) -> str:
    tag = re.sub(r'\sreferrerpolicy="[^"]*"', "", tag)
    rel = re.search(r'\srel="([^"]*)"', tag)
    words = [w for w in (rel.group(1).split() if rel else []) if w != "noreferrer"]
    if rel:
        tag = tag[:rel.start()] + tag[rel.end():]
    if own_site(url):
        extra = ' referrerpolicy="strict-origin"'
    else:
        words.append("noreferrer")
        extra = ""
    if words:
        extra = f' rel="{" ".join(words)}"' + extra
    return tag[:-1] + extra + ">"


# Where a visit to another of Boréale's sites came from, for Umami (workbench's
# "Mesure d'audience"): a link from this site to another *.boreale.dev site
# carries utm_source='ha' and a utm_medium telling where on the page it is:
# "nav" (the header, its sites menu), "footer", or "link" (the page's text).
UTM_SOURCE = "ha"


def utm(url: str, medium: str) -> str:
    """`url` (as written in the page's HTML) tagged for its medium, or as it is
    when it leads out of Boréale's sites."""
    u = urlsplit(html.unescape(url))
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not (host == "boreale.dev" or host.endswith(".boreale.dev")):
        return url
    query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.startswith("utm_")]
    if host != (urlsplit(SITE_URL).hostname or ""):
        query += [("utm_source", UTM_SOURCE), ("utm_medium", medium)]
    tagged = urlunsplit(u._replace(query=urlencode(query)))
    return url if tagged == html.unescape(url) else html.escape(tagged, quote=True)


def links_out(text: str) -> str:
    main, footer = text.find("<main"), text.find("<footer")

    def one(m):
        at = m.start()
        medium = "footer" if 0 <= footer <= at else "nav" if main < 0 or at < main else "link"
        url = utm(m.group(1), medium)
        tag = m.group(0).replace(f'href="{m.group(1)}"', f'href="{url}"', 1)
        return link_out(tag, url)

    return LINK_OUT.sub(one, text)


def links_out(text: str) -> str:
    main, footer = text.find("<main"), text.find("<footer")

    def one(m):
        at = m.start()
        medium = "footer" if 0 <= footer <= at else "nav" if main < 0 or at < main else "link"
        url = utm(m.group(1), medium)
        tag = m.group(0).replace(f'href="{m.group(1)}"', f'href="{url}"', 1)
        return link_out(tag, url)

    return LINK_OUT.sub(one, text)


def flag(language: str) -> str:
    """A language's flag, two regional indicator letters, for the eyes only."""
    emoji = "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in FLAGS[language])
    return f'<span class="flag" aria-hidden="true">{emoji}</span>'


def languages(language: str, catalog: dict, root: str, path: str) -> str:
    """The header's languages: a button with the page's, and under it their
    menu (a popover, as the menu of Boréale's sites), this page in each, its
    own marked. Choosing one keeps it (assets/lang.js)."""
    name = next(n for c, _, n, _ in LANGUAGES if c == language)
    options = "\n".join(
        f'        <li><a href="{root}{folder(c)}{path}" data-lang="{d or c}" lang="{hl}" hreflang="{hl}"'
        f'{' aria-current="true"' if c == language else ""}>{flag(c)}{html.escape(n)}</a></li>'
        for c, d, n, hl in LANGUAGES)
    label = catalog["language"]
    return (f'<div class="settings">\n'
            f'      <button class="lang-button" type="button" popovertarget="languages" aria-label="{label} · {html.escape(name)}">'
            f'{flag(language)}<span class="lang-name">{html.escape(name)}</span>'
            f'<span class="lang-code">{language.split("-")[0].upper()}</span>'
            f'<svg class="chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button>\n'
            f'      <ul id="languages" class="langs" popover aria-label="{label}">\n{options}\n      </ul>\n    </div>')

# Boréale's sites, in the header's menu (switcher()), as boreale.dev's (the
# reference), with this one under the integrations.
SITES = [(None, [("boreale", "Boréale", "https://boreale.dev/")]),
         ("sites_homebrew", [("playguard", "PlayGuard", "https://guard.boreale.dev/"),
                             ("playshelf", "PlayShelf", "https://shelf.boreale.dev/")]),
         ("sites_integrations", [("ha", "Home Assistant", "https://ha.boreale.dev/")]),
         ("sites_libraries", [("aurore", "Aurore", "https://aurore.boreale.dev/")]),
         ("sites_open", [("atlas", "Atlas", "https://atlas.boreale.dev/"),
                         ("lantern", "Lantern", "https://lantern.boreale.dev/")])]
HERE = "ha"


def switcher(language: str, catalog: dict, root: str, latest: dict) -> str:
    """The header's name, a button that opens the menu of Boréale's sites
    (site.css's and site.js's "site switcher", boreale.dev's), this one
    marked and leading home, each with its latest release (`latest`)."""
    label = catalog["sites_label"]
    groups = []
    for title, sites in SITES:
        items = []
        for key, name, url in sites:
            here = key == HERE
            href = f"{root}{folder(language)}" if here else url + folder(language)
            soon = f'<em class="soon">{catalog["sites_soon"]}</em>' if key == "playshelf" else ""
            version = f' <span class="sites-version">{html.escape(latest[key])}</span>' if key in latest else ""
            current = ' aria-current="true"' if here else ""
            items.append(f'<li><a href="{href}"{current}>'
                         f'<img src="{root}assets/marks/{key}.svg" alt="" width="36" height="36">'
                         f'<span><strong>{name}{version}</strong><small>{catalog[f"sites_{key}"]}</small></span>{soon}</a></li>')
        heading = f'<p class="sites-title">{catalog[title]}</p>' if title else ""
        groups.append(f'        {heading}<ul>\n          ' + "\n          ".join(items) + '\n        </ul>')
    return (f'<div class="switcher">\n'
            f'      <button class="brand switch" type="button" popovertarget="sites" aria-label="Boréale · {label}">'
            f'<img src="{root}assets/marks/{HERE}.svg" alt="" width="34" height="34">Boréale'
            f'<svg class="chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></button>\n'
            f'      <div id="sites" class="sites" popover aria-label="{label}">\n'
            + "\n".join(groups) + '\n      </div>\n    </div>')


# The pages other than 404.html, by their path under each language's folder.
PAGES = {"": "home.html", "legal/": "legal.html"}

KEY = re.compile(r"\{\{([a-z0-9_]+)\}\}")


def fill(text: str, values: dict) -> str:
    def one(match):
        key = match.group(1)
        if key not in values:
            sys.exit(f"build_site: no text for {{{{{key}}}}}")
        return values[key]
    # Twice: a text may hold a key ({{root}} in home.html's links).
    return KEY.sub(one, KEY.sub(one, text))


def fetch(url: str) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "boreale-ha-site"}
    if os.environ.get("GITHUB_TOKEN") and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as answer:
        return json.load(answer)


def versions() -> dict:
    """The projects' latest versions, for the menu of Boréale's sites: the
    others' from boreale.dev's versions.json, this one's from GitHub (none
    offline, or when they cannot be read: the site builds without them)."""
    if os.environ.get("SITE_OFFLINE") == "1":
        return {}
    latest = {}
    try:
        doc = fetch(VERSIONS_URL)
        projects = doc.get("projects", doc) if isinstance(doc, dict) else {}
        latest.update({k: v for k, v in projects.items() if isinstance(v, str)})
    except Exception as error:
        print(f"build_site: {VERSIONS_URL} not read ({error})", file=sys.stderr)
    try:
        release = fetch(f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest")
        latest[HERE] = release["tag_name"].lstrip("v")
    except Exception as error:
        print(f"build_site: the latest release not read ({error})", file=sys.stderr)
    return latest


def structured(language: str, catalog: dict, latest: dict) -> str:
    """schema.org data for search engines: the integration, by Boréale."""
    item = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Boréale for Nintendo Switch",
            "url": address(language), "description": catalog["description"], "inLanguage": html_lang(language),
            "applicationCategory": "HomeAutomationApplication", "operatingSystem": "Home Assistant",
            "license": "https://www.gnu.org/licenses/gpl-3.0.html",
            "sameAs": f"https://github.com/{OWNER}/{REPO}",
            "publisher": {"@type": "Organization", "name": "Boréale", "url": "https://boreale.dev/"}}
    if HERE in latest:
        item["softwareVersion"] = latest[HERE]
    text = json.dumps(item, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>'


def attribute(text: str) -> str:
    """A text for a double-quoted attribute (the apostrophes left as they are)."""
    return html.escape(text, quote=False).replace('"', "&quot;")


def indexing(url: str, path: str, lost: bool) -> str:
    """The canonical address and the other languages' for search engines; a
    page that is not there (404.html) is kept out of their index instead."""
    if lost:
        return '<meta name="robots" content="noindex">'
    lines = [f'<link rel="canonical" href="{url}">']
    lines += [f'<link rel="alternate" hreflang="{hl}" href="{address(code, path)}">' for code, _, _, hl in LANGUAGES]
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{address(CODES[0], path)}">')
    return "\n".join(lines)


def folder(language: str) -> str:
    """A language's folder: none for the first one, at the root."""
    d = next(d for c, d, _, _ in LANGUAGES if c == language)
    return f"{d}/" if d else ""


def html_lang(language: str) -> str:
    """A language's code for html's lang and hreflang (pt-PT for pt)."""
    return next(hl for c, _, _, hl in LANGUAGES if c == language)


def address(language: str, path: str = "") -> str:
    """A page's address in a language (its home page without a path)."""
    return SITE_URL + folder(language) + path


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
    values["version"] = (catalog["hero_version"].replace("{version}", html.escape(latest[HERE]))
                         if HERE in latest else "")
    values["legal_translation"] = ("" if language == ORIGINAL else
                                   f'<p class="translation">{catalog["legal_translation"]}</p>')
    values["lang"] = html_lang(language)
    values["home"] = folder(language)
    values["og_locale"] = OG_LOCALES[language]
    values["languages"] = languages(language, catalog, root, path if not lost else "")
    values["first_visit"] = " data-first-visit" if first_visit else ""
    values["lost"] = f' data-lost="{root}"' if lost and language == CODES[0] else ""
    values["indexing"] = indexing(url, path, lost)
    values["page_class"] = ' class="home"' if hero else ""
    values["og_alternates"] = "\n".join(
        f'<meta property="og:locale:alternate" content="{OG_LOCALES[code]}">' for code in CODES if code != language)
    values.update(root=root, site=SITE_URL, url=url, title=title)
    values["switcher"] = switcher(language, catalog, root, latest)
    values["jsonld"] = structured(language, catalog, latest)
    values["hero"] = fill(hero, values)
    values["body"] = fill(body, values)
    return links_out(fill((SITE / "template.html").read_text(encoding="utf-8"), values))


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

    hero = (SITE / "hero.html").read_text(encoding="utf-8")
    bodies = {path: (SITE / name).read_text(encoding="utf-8") for path, name in PAGES.items()}
    lost = (SITE / "lost.html").read_text(encoding="utf-8")
    base = urlparse(SITE_URL).path  # 404.html is served at any depth
    catalogs = {code: json.loads((SITE / "i18n" / f"{code}.json").read_text(encoding="utf-8")) for code in CODES}
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
    urls = ""
    for path in PAGES:
        alternates = "".join(
            f'    <xhtml:link rel="alternate" hreflang="{hl}" href="{address(code, path)}"/>\n' for code, _, _, hl in LANGUAGES)
        alternates += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{address(CODES[0], path)}"/>\n'
        urls += "".join(f"  <url>\n    <loc>{address(code, path)}</loc>\n{alternates}  </url>\n" for code in CODES)
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
        f' xmlns:xhtml="http://www.w3.org/1999/xhtml">\n{urls}</urlset>\n', encoding="utf-8")
    (out / ".nojekyll").touch()
    digest = hashlib.sha256()
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        digest.update(path.relative_to(out).as_posix().encode() + b"\0" + path.read_bytes())
    (out / "build.sha256").write_text(digest.hexdigest() + "\n", encoding="utf-8")
    print(f"build_site: {len(CODES)} languages in {out} for {SITE_URL}")


if __name__ == "__main__":
    main()

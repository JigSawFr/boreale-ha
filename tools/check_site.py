#!/usr/bin/env python3
"""Checks a built ha.boreale.dev (tools/build_site.py) and its sources, as
boreale.dev's tools/check_site.py does its own.

    python3 tools/check_site.py <site-dir>

- every catalog of site/i18n/ has the same keys as en.json, none empty (but
  fr.json's legal_translation: the French legal page is the original);
- no {{key}} left in a page;
- every link and image to the site leads to a file, and every #anchor to an id;
- links out by the rule "liens sortants anonymes": every page sends no
  referrer, a link to a third party has rel="noreferrer", one to
  *.boreale.dev or github.com/JigSawFr has referrerpolicy="strict-origin";
  one to another of our sites has utm_source=ha and a utm_medium, no
  other link has utm_ parameters;
- nothing the Content-Security-Policy blocks: no inline script (but the
  schema.org data, which runs nothing), no <style>, no style="" attribute,
  nothing loaded from another site;
- the schema.org data, sitemap.xml and manifest.webmanifest read as JSON or XML.
"""
import json
import os
import sys
import xml.etree.ElementTree as ElementTree
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

ROOT = Path(__file__).resolve().parent.parent



def own_site(url: str) -> bool:
    """boreale.dev, its subdomains, and the repositories of github.com/JigSawFr/
    (that account's alone: another owner, a gist or GitHub's own pages are
    third parties)."""
    u = urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and (host == "boreale.dev" or host.endswith(".boreale.dev") or
                                    (host == "github.com" and u.path.lower().startswith("/jigsawfr/")))


def check_own_site() -> None:
    """own_site() against look-alikes, at each run (the site has no unit tests)."""
    for url in ("https://boreale.dev/", "https://shelf.boreale.dev/fr/", "https://github.com/JigSawFr/PlayShelf",
                "https://github.com/jigsawfr/boreale/releases"):
        assert own_site(url), url
    for url in ("https://store.example.com/app/1", "https://github.com/JigSawFr", "https://github.com/jigsawfrx/x",
                "https://github.com/someone/JigSawFr", "https://gist.github.com/JigSawFr/1",
                "https://boreale.dev.example.com/", "https://notboreale.dev/", "http://boreale.dev/"):
        assert not own_site(url), url


# This site's address (build_site.py's SITE_URL) and its name in the UTM tags
# of its links to our other sites.
SITE_HOST = (urlparse(os.environ.get("SITE_URL", "https://ha.boreale.dev/")).hostname or "").lower()
UTM_SOURCE = "ha"


def link_problem(attrs: dict) -> str:
    """What a link out does wrong by the rule "liens sortants anonymes": a
    third party gets rel="noreferrer"; *.boreale.dev and github.com/JigSawFr
    keep the origin alone (referrerpolicy="strict-origin", no noreferrer)."""
    href = attrs.get("href") or ""
    if urlparse(href).scheme not in ("http", "https"):
        return ""
    rel = (attrs.get("rel") or "").split()
    if own_site(href):
        if "noreferrer" in rel or attrs.get("referrerpolicy") != "strict-origin":
            return f'link to {href} needs referrerpolicy="strict-origin" and no noreferrer'
    elif "noreferrer" not in rel:
        return f'link to {href} without rel="noreferrer"'
    # UTM tags (workbench's "Mesure d'audience"): a link to another of our
    # sites (*.boreale.dev) says where it comes from, utm_source='ha' and
    # a utm_medium; one to this site itself or to anyone else carries none.
    u = urlparse(href)
    host = (u.hostname or "").lower()
    query = dict(parse_qsl(u.query))
    if u.scheme == "https" and (host == "boreale.dev" or host.endswith(".boreale.dev")) and host != SITE_HOST:
        if query.get("utm_source") != UTM_SOURCE or not query.get("utm_medium"):
            return f"link to {href} without utm_source={UTM_SOURCE} and a utm_medium"
    elif any(k.startswith("utm_") for k in query):
        return f"link to {href} with utm_ parameters: only a link to another of our sites has them"
    return ""


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.problems, self.data = set(), [], [], []
        self.in_data = False
        self.no_referrer = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "referrer" and a.get("content") == "no-referrer":
            self.no_referrer = True
        if tag == "a" and link_problem(a):
            self.problems.append(link_problem(a))
        if "id" in a:
            self.ids.add(a["id"])
        if "style" in a:
            self.problems.append(f"style attribute on <{tag}>")
        if tag == "style":
            self.problems.append("<style> element")
        if tag == "script":
            if a.get("type") == "application/ld+json":
                self.in_data = True
                return
            if not a.get("src"):
                self.problems.append("inline <script>")
            self.links.append(("src", a.get("src") or ""))
        for name in ("href", "src"):
            if name in a and not (tag == "script" and name == "src"):
                self.links.append((name, a[name]))

    def handle_data(self, data):
        if self.in_data:
            self.data.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False


def main() -> None:
    check_own_site()
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    site = Path(sys.argv[1])
    errors = []

    catalogs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "site/i18n").glob("*.json"))}
    reference = set(catalogs["en"])
    for lang, catalog in catalogs.items():
        # fr.json has no legal_translation: its legal page is the original.
        for key in sorted(reference - set(catalog) - ({"legal_translation"} if lang == "fr" else set())):
            errors.append(f"i18n/{lang}.json: no {key}")
        for key in sorted(set(catalog) - reference):
            errors.append(f"i18n/{lang}.json: {key} is not in en.json")
        for key, text in catalog.items():
            if not str(text).strip():
                errors.append(f"i18n/{lang}.json: {key} is empty")

    pages = sorted(site.rglob("*.html"))
    if not pages:
        errors.append(f"no page in {site}")
    for path in pages:
        name = path.relative_to(site)
        html = path.read_text(encoding="utf-8")
        if "{{" in html:
            errors.append(f"{name}: a {{{{key}}}} is left")
        parsed = Page()
        parsed.feed(html)
        errors += [f"{name}: {p}" for p in parsed.problems]
        if not parsed.no_referrer:
            errors.append(f"{name}: no <meta name=\"referrer\" content=\"no-referrer\">")
        try:
            json.loads("".join(parsed.data) or "{}")
        except ValueError as error:
            errors.append(f"{name}: its schema.org data is not JSON ({error})")
        for attr, link in parsed.links:
            url = urlparse(link)
            if url.scheme in ("http", "https", "mailto"):
                if attr == "src":
                    errors.append(f"{name}: loads {link} from another site")
                continue
            if name.name == "404.html" and url.path.startswith("/"):
                target = site / url.path.lstrip("/")  # served from the site's root
            else:
                target = (path.parent / url.path).resolve() if url.path else path
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                errors.append(f"{name}: {link} leads nowhere")
                continue
            if url.fragment and target == path and url.fragment not in parsed.ids:
                errors.append(f"{name}: #{url.fragment} is not on the page")

    for name in ("sitemap.xml",):
        try:
            ElementTree.parse(site / name)
        except (OSError, ElementTree.ParseError) as error:
            errors.append(f"{name}: {error}")
    try:
        icons = json.loads((site / "manifest.webmanifest").read_text(encoding="utf-8"))["icons"]
        errors += [f"manifest.webmanifest: {i['src']} leads nowhere" for i in icons if not (site / i["src"]).exists()]
    except (OSError, ValueError, KeyError) as error:
        errors.append(f"manifest.webmanifest: {error}")

    for e in errors:
        print(f"check_site: {e}")
    if errors:
        sys.exit(1)
    print(f"check_site: {len(pages)} pages, {len(catalogs)} catalogs, nothing wrong")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Checks a built ha.boreale.dev (tools/build_site.py) and its sources.

    python3 tools/check_site.py <site-dir>

- what every one of Boréale's sites passes (library/boreale-site,
  boreale_site.check): the page chrome (one header with the menu of Boréale's
  sites, the nav, the pill before GitHub, the footer, chrome.css and
  chrome.js), no {{key}} left, links and #anchors that lead
  somewhere, links out by the rule "liens sortants anonymes" and their UTM
  tags, nothing the Content-Security-Policy blocks, Umami's tracker, no
  e-mail address, the schema.org data read as JSON;
- the catalogs of site/i18n/ and boreale-site's: the same keys as en-US.json,
  none empty (but fr.json's legal_translation: the French legal page is the
  original), no common text repeated here;
- sitemap.xml reads as XML, manifest.webmanifest's icons are there.
"""
import json
import os
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "library" / "boreale-site"))
import boreale_site as boreale  # noqa: E402
from boreale_site import check  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    site = Path(sys.argv[1])
    errors = boreale.check_catalogs(ROOT / "site" / "i18n", optional={"fr": {"legal_translation"}})
    found, pages = check.pages(site, boreale.Site("ha", os.environ.get("SITE_URL")), chrome=True)
    errors += found

    try:
        ElementTree.parse(site / "sitemap.xml")
    except (OSError, ElementTree.ParseError) as error:
        errors.append(f"sitemap.xml: {error}")
    try:
        icons = json.loads((site / "manifest.webmanifest").read_text(encoding="utf-8"))["icons"]
        errors += [f"manifest.webmanifest: {i['src']} leads nowhere" for i in icons if not (site / i["src"]).exists()]
    except (OSError, ValueError, KeyError) as error:
        errors.append(f"manifest.webmanifest: {error}")

    for e in errors:
        print(f"check_site: {e}")
    if errors:
        sys.exit(1)
    print(f"check_site: {pages} pages, {len(boreale.CODES)} catalogs, nothing wrong")


if __name__ == "__main__":
    main()

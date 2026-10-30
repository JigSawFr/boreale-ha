// The language at a first visit: the English home page (the root, marked
// data-first-visit) sends a visitor whose browser prefers one of the site's
// other languages to its folder (/fr/, /de/, /zh-hant/...), unless a
// language was chosen before. Choosing one in the header's menu keeps it.
// The page not found (404.html) follows the same choice.
// Loaded in <head>, before the page is drawn, so the move shows nothing.
(function () {
  const KEY = "boreale-lang";
  // The site's languages by their folder (build_site.py's LANGUAGES); the
  // first, English, at the root.
  const SITE = ["en", "fr", "fr-ca", "de", "es", "es-419", "it", "nl", "pt", "pt-br", "ru", "ja", "ko",
    "zh-hans", "zh-hant"];
  let chosen = null;
  try { chosen = localStorage.getItem(KEY); } catch (e) { /* storage refused: no memory */ }

  const root = document.documentElement;
  // The browser's first language the site has (English stops the search):
  // Canada's French, Spain's Spanish or Latin America's, Brazil's Portuguese
  // or Portugal's, Traditional Chinese (Taiwan, Hong Kong, Macao) or Simplified.
  const browser = () => {
    for (const tag of navigator.languages || [navigator.language || ""]) {
      const t = String(tag).toLowerCase();
      const [base, region = ""] = t.split("-");
      if (base === "en") return null;
      if (base === "fr") return region === "ca" ? "fr-ca" : "fr";
      if (base === "es") return !region || region === "es" ? "es" : "es-419";
      if (base === "pt") return region === "br" ? "pt-br" : "pt";
      if (base === "zh") return ["tw", "hk", "mo", "hant"].includes(region) || t.includes("hant") ? "zh-hant" : "zh-hans";
      if (SITE.includes(base)) return base;
    }
    return null;
  };
  if (root.hasAttribute("data-first-visit") && !chosen) {
    const wanted = browser();
    if (wanted && wanted !== SITE[0]) {
      location.replace(`${wanted}/${location.hash}`);
      return;
    }
  }

  // A page that is not there: GitHub Pages serves the root's 404.html (in
  // the first language, data-lost holding the site's path) at any address.
  // It sends to the 404.html of the language the address is in (/fr/...),
  // else of the one chosen, else of the browser's.
  const base = root.getAttribute("data-lost");
  if (base !== null) {
    const inPath = location.pathname.startsWith(base) && location.pathname.slice(base.length).split("/")[0].toLowerCase();
    const wanted = SITE.includes(inPath) ? inPath : SITE.includes(chosen) ? chosen : browser();
    if (wanted && wanted !== SITE[0]) {
      location.replace(`${base}${wanted}/404.html`);
      return;
    }
  }

  // A language chosen in the header's menu (its links' data-lang, the folder).
  document.addEventListener("click", (event) => {
    const link = event.target.closest && event.target.closest("a[data-lang]");
    if (!link) return;
    try { localStorage.setItem(KEY, link.getAttribute("data-lang")); } catch (e) { /* idem */ }
  });
})();

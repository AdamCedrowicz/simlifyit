"""Trzy sposoby wykrywania z monitor-garazy.ps1: linki, linie tekstu, głębokie sprawdzanie podstron."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urldefrag

from bs4 import BeautifulSoup, NavigableString

from monitor.core.textparse import normalize
from monitor.garaze.rules import GARAGE, STRONG, WEAK, is_sale_hit

GENERIC_LINK = re.compile(r"^\s*(więcej|wiecej|zobacz|czytaj( dalej| więcej)?|szczegóły|szczegoly|dalej|"
                          r"pokaż|pokaz|rozwiń|>>|»|\.\.\.)\s*[»>.]*\s*$", re.I)
SKIP_EXT = re.compile(r"\.(pdf|docx?|xlsx?|odt|ods|rtf|zip|rar|7z|jpe?g|png|gif|webp|bmp|tiff?|mp4|mp3)(\?|$)", re.I)
ANNOUNCEMENT = re.compile(r"ogłosz|oglosz|przetarg|wykaz|zbyci|sprzeda|licytac|aukcj|nieruchomo", re.I)
BREADCRUMB = re.compile(r"(\s[>»/|]\s.*){2,}")
BLOCK_TAGS = ["p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "div", "td", "dd", "dt", "article", "section"]


@dataclass
class Hit:
    key: str
    url: str          # gdzie kliknąć
    snippet: str
    method: str       # link | tekst | podstrona


@dataclass
class Page:
    url: str
    soup: BeautifulSoup
    lines: list[str]
    links: list[tuple[str, str, str]]  # (absolutny url, tekst linku, tekst przed linkiem)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_page(html: str, url: str) -> Page:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    title = _clean(soup.title.get_text()) if soup.title else ""
    for t in soup.select("nav, [class*=breadcrumb], [id*=breadcrumb], [class*=okruszk]"):
        t.decompose()
    lines = _text_lines(soup, title)
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        abs_url = urldefrag(urljoin(url, href))[0]
        links.append((abs_url, _clean(a.get_text(" ")), _text_before(a, 200)))
    return Page(url, soup, lines, links)


def _text_lines(soup: BeautifulSoup, title: str) -> list[str]:
    body = soup.body or soup
    for br in body.find_all("br"):
        br.replace_with("\n")
    for tag in body.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    out, seen = [], set()
    for raw in body.get_text().split("\n"):
        line = _clean(raw)
        if len(line) < 8 or line == title or BREADCRUMB.search(line) or line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def _text_before(a, limit: int) -> str:
    parts, total = [], 0
    for el in a.previous_elements:
        if isinstance(el, NavigableString):
            s = str(el)
            parts.append(s)
            total += len(s)
            if total >= limit:
                break
    return _clean("".join(reversed(parts)))[-limit:]


def link_text(text: str, before: str) -> str:
    """Ogólny link „więcej/zobacz” dostaje tekst sprzed siebie (do 200 znaków)."""
    if not text or GENERIC_LINK.match(text):
        return _clean(f"{before} {text}")
    return text


def find_hits(page: Page, opts: dict) -> tuple[list[Hit], list[str]]:
    """Zwraca trafienia z linków i linii tekstu oraz listę podstron do głębokiego sprawdzenia."""
    inc_p, inc_r = opts.get("includeParkingSpaces", False), opts.get("includeRental", False)
    hits: dict[str, Hit] = {}
    deep: list[str] = []
    hit_texts: set[str] = set()
    for url, text, before in page.links:
        t = link_text(text, before)
        if is_sale_hit(t, inc_p, inc_r):
            hits.setdefault(f"url:{url}", Hit(f"url:{url}", url, t[:300], "link"))
            hit_texts.add(normalize(t, 10_000))
        elif (not GARAGE.search(t) and ANNOUNCEMENT.search(t) and not SKIP_EXT.search(url)
              and url != page.url and url not in deep):
            deep.append(url)
    for line in page.lines:
        if not is_sale_hit(line, inc_p, inc_r):
            continue
        n = normalize(line)
        if any(n[:80] in h for h in hit_texts):  # linia to tekst linku, który już jest trafieniem
            continue
        key = f"text:{page.url}|{n}"
        hits.setdefault(key, Hit(key, page.url, line[:300], "tekst"))
    return list(hits.values()), deep


def deep_hits(sub: Page, list_lines: set[str], opts: dict) -> list[str]:
    """Fragmenty podstrony mówiące o sprzedaży garażu, bez linii wspólnych ze stroną listy."""
    inc_p, inc_r = opts.get("includeParkingSpaces", False), opts.get("includeRental", False)
    out = []
    for line in sub.lines:
        if line in list_lines:
            continue
        if is_sale_hit(line, inc_p, inc_r):
            out.append(line[:300])
    if not out:
        # zdarza się, że „garaż” i „sprzedaż” są w różnych liniach: sprawdź całość treści
        body = " ".join(l for l in sub.lines if l not in list_lines)
        if GARAGE.search(body) and (STRONG.search(body) or WEAK.search(body)) and is_sale_hit(body, inc_p, inc_r):
            m = GARAGE.search(body)
            out.append(body[max(0, m.start() - 150):m.start() + 150])
    return out

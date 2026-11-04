"""Ogólny parser list ogłoszeń (Adradar, komornik, KAS, KOWR, BIP...).

Konfiguracja w YAML: urls, link_pattern (regex adresu oferty), render (http|browser), category.
Oferta = link pasujący do wzorca + tekst najbliższego „kafelka” wokół niego.
"""
from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup

from monitor.core.offer import Offer
from monitor.core.textparse import parse_area_m2, parse_date, parse_price, parse_signature
from monitor.sources.common import get_page

GENERIC = re.compile(r"^\s*(więcej|wiecej|zobacz|szczegóły|szczegoly|czytaj dalej|pokaż|>>|»)\s*$", re.I)


def _container_text(a, url_of, max_len: int = 1500) -> str:
    """Tekst najwyższego przodka, który zawiera linki tylko do tej jednej oferty."""
    me = url_of(a)
    node, best = a, a.get_text(" ", strip=True)
    while node.parent is not None and node.parent.name not in ("body", "html", "[document]"):
        t = node.parent.get_text(" ", strip=True)
        if len(t) > max_len:
            break
        others = {url_of(x) for x in node.parent.find_all("a", href=True)} - {me, None}
        if others:  # rodzic obejmuje już inną ofertę – to lista, nie kafelek
            break
        node, best = node.parent, t
    return re.sub(r"\s+", " ", best)


def parse_listing(html: str, base_url: str, cfg: dict, source_name: str) -> list[Offer]:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    pat = re.compile(cfg["link_pattern"])
    exclude = re.compile(cfg["exclude_pattern"]) if cfg.get("exclude_pattern") else None
    offers: dict[str, Offer] = {}

    def url_of(a):
        u = urldefrag(urljoin(base_url, a["href"].strip()))[0]
        return u if pat.search(u) and not (exclude and exclude.search(u)) else None

    for a in soup.find_all("a", href=True):
        url = url_of(a)
        if not url:
            continue
        text = _container_text(a, url_of)
        title = a.get_text(" ", strip=True)
        if not title or GENERIC.match(title) or len(title) < 5:
            title = text[:140]
        if url in offers:  # kilka linków do tej samej oferty: weź dłuższy opis
            if len(text) > len(offers[url].description):
                offers[url].description = text
            continue
        offers[url] = Offer(
            source=source_name, url=url, title=title[:200], category=cfg.get("category", ""),
            location=cfg.get("location", ""), description=text,
            area_m2=parse_area_m2(text), price=parse_price(text),
            auction_date=parse_date(text), signature=parse_signature(text),
        )
        offers[url].extra["location_from"] = "config" if cfg.get("location") else ""
    return list(offers.values())


def fetch(cfg: dict, ctx) -> list[Offer]:
    out = []
    for i, url in enumerate(cfg["urls"]):
        html = get_page(url, cfg, ctx, f"{cfg['name']}-{i}")
        out += parse_listing(html, url, cfg, cfg["name"])
    if not out and cfg.get("expect_offers", True):
        raise RuntimeError("0 ofert: wzorzec linków nie pasuje albo strona zablokowała automat")
    return out

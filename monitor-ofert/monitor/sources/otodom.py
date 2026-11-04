"""Otodom: dane z <script id="__NEXT_DATA__"> (JSON). Struktura bywa zmieniana – szukamy ogłoszeń „po kształcie”."""
from __future__ import annotations

import json
import re

from monitor.core.offer import Offer
from monitor.sources.common import get_page

BASE = "https://www.otodom.pl/pl/oferta/"


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _num(v):
    if isinstance(v, dict):
        v = v.get("value")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _location(ad: dict) -> str:
    loc = ad.get("location") or {}
    names = []
    for k in ("city", "county", "province"):
        x = (loc.get("address") or {}).get(k)
        if isinstance(x, dict) and x.get("name"):
            names.append(x["name"])
    if not names:
        for l in ((loc.get("reverseGeocoding") or {}).get("locations") or []):
            if l.get("fullName"):
                return l["fullName"]
    return ", ".join(names)


def parse_next_data(html: str, source_name: str) -> list[Offer]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("brak __NEXT_DATA__ (blokada albo zmiana strony)")
    data = json.loads(m.group(1))
    out, seen = [], set()
    for d in _walk(data):
        if not (isinstance(d.get("slug"), str) and isinstance(d.get("title"), str)):
            continue
        if "totalPrice" not in d and "price" not in d:
            continue
        url = BASE + d["slug"]
        if url in seen:
            continue
        seen.add(url)
        area = _num(d.get("areaInSquareMeters")) or _num(d.get("terrainAreaInSquareMeters"))
        o = Offer(source=source_name, url=url, title=d["title"], category="grunty",
                  location=_location(d), area_m2=area,
                  price=_num(d.get("totalPrice")) or _num(d.get("price")),
                  description=d.get("shortDescription") or "")
        coords = ((d.get("location") or {}).get("coordinates") or {})
        if coords.get("latitude"):
            o.lat, o.lon = float(coords["latitude"]), float(coords["longitude"])
        out.append(o)
    return out


def fetch(cfg: dict, ctx) -> list[Offer]:
    out = []
    for i, url in enumerate(cfg["urls"]):
        html = get_page(url, cfg, ctx, f"{cfg['name']}-{i}")
        out += parse_next_data(html, cfg["name"])
    return out

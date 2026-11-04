"""Raport e-mail działek (rozdział 5.6)."""
from __future__ import annotations

import html
from collections import OrderedDict

from monitor.core.offer import Offer

GEOPORTAL = "https://mapy.geoportal.gov.pl/imap/Imgp_2.html?identifyParcel="


def _zl(v) -> str:
    return "–" if v is None else f"{v:,.0f} zł".replace(",", " ")


def _sort_key(o: Offer):
    e = o.extra
    if e.get("zl_ha_przel"):
        return (0, e["zl_ha_przel"])
    best = max((e.get("scores") or {}).values(), default=0)
    return (1, -best)


def offer_html(o: Offer) -> str:
    e = o.extra
    esc = html.escape
    rows = []
    loc = o.location or (e.get("parcel") or {}).get("commune", "")
    dist = e.get("distance_km")
    rows.append(f"<b>{esc(o.title)}</b>")
    rows.append(f"{esc(loc)}" + (f" · {dist:.1f} km od Jackowa" if dist is not None else " · odległość nieznana")
                + (" (przybliżona)" if e.get("distance_approx") else ""))
    area = o.area_m2 or (e.get("parcel") or {}).get("area_m2")
    parts = []
    if area:
        parts.append(f"{area:,.0f} m²".replace(",", " "))
    parts.append(("cena wywołania " if o.start_price else "cena ") + _zl(o.effective_price))
    if e.get("zl_m2"):
        parts.append(f"{e['zl_m2']:.2f} zł/m²")
    if e.get("ha_przel") is not None:
        parts.append(f"{e['ha_przel']:.4f} ha przel.")
    if e.get("zl_ha_przel"):
        parts.append(f"<b>{_zl(e['zl_ha_przel'])} / ha przel.</b>")
    if e.get("pct_oszacowania"):
        parts.append(f"{e['pct_oszacowania']}% oszacowania")
    rows.append(" · ".join(parts))
    if e.get("uzytki"):
        rows.append("Użytki: " + esc(", ".join(e["uzytki"])) + f" <small>({esc(e.get('ha_przel_zrodlo', ''))})</small>")
    if o.auction_date or o.signature:
        rows.append(" · ".join(x for x in [f"termin: {o.auction_date}" if o.auction_date else "",
                                           f"sygn.: {esc(o.signature)}" if o.signature else ""] if x))
    if e.get("scores"):
        rows.append("Ocena: " + ", ".join(f"{k} {v}" for k, v in e["scores"].items()))
    if e.get("flags"):
        rows.append("Flagi: " + esc("; ".join(e["flags"])))
    links = [f"<a href='{esc(o.url)}'>ogłoszenie</a>"]
    if (e.get("parcel") or {}).get("id"):
        pid = e["parcel"]["id"]
        links.append(f"<a href='{GEOPORTAL}{esc(pid)}'>Geoportal {esc(pid)}</a>")
    for c in e.get("candidates", []):
        links.append(f"<a href='{GEOPORTAL}{esc(c['id'])}'>kandydat {esc(c['id'])} ({c['confidence']:.0%})</a>")
    if e.get("also_in"):
        links.append("także w: " + esc(", ".join(e["also_in"])))
    rows.append(" · ".join(links))
    return "<li style='margin-bottom:10px'>" + "<br>".join(rows) + "</li>"


def build_report(offers: list[Offer], failed: list[tuple[str, str, str]], manual: list[tuple[str, str]]) -> tuple[str, str]:
    ranked = sorted(offers, key=_sort_key)
    best = next((o.extra["zl_ha_przel"] for o in ranked if o.extra.get("zl_ha_przel")), None)
    subject = f"Działki: {len(offers)} nowych ofert" + (f" (najlepsza: {_zl(best)}/ha przel.)" if best else "")
    top = ranked[:5]
    out = [f"<h2>{html.escape(subject)}</h2>", "<h3>Top 5</h3><ul>", *map(offer_html, top), "</ul>"]
    auctions = sorted([o for o in offers if o.auction_date], key=lambda o: o.auction_date)
    if auctions:
        out.append("<h3>Najbliższe terminy licytacji</h3><ul>")
        for o in auctions[:10]:
            out.append(f"<li>{o.auction_date} · {html.escape(o.title)} · {_zl(o.effective_price)}"
                       + (f" · sygn. {html.escape(o.signature)}" if o.signature else "")
                       + f" · <a href='{html.escape(o.url)}'>link</a></li>")
        out.append("</ul>")
    rest = [o for o in ranked if o not in top]
    if rest:
        groups: OrderedDict[str, list[Offer]] = OrderedDict()
        for o in rest:
            groups.setdefault(o.source, []).append(o)
        out.append("<h3>Pozostałe nowe oferty</h3>")
        for src, items in groups.items():
            out.append(f"<h4>{html.escape(src)} ({len(items)})</h4><ul>" + "".join(map(offer_html, items)) + "</ul>")
    out += _sources_section(failed, manual)
    out.append("<p><small>Monitor wskazuje okazje, ale nie zastępuje sprawdzenia księgi wieczystej, operatu, "
               "dojazdu i stanu prawnego. Klasy gleby i okręgi podatkowe mogą być niepełne.</small></p>")
    return subject, "\n".join(out)


def _sources_section(failed, manual) -> list[str]:
    if not failed and not manual:
        return []
    out = ["<h3>Źródła niedziałające / do ręcznego przeglądu</h3><ul>"]
    for name, url, err in failed:
        out.append(f"<li>{html.escape(name)}: {html.escape(err[:150])} – <a href='{html.escape(url)}'>sprawdź ręcznie</a></li>")
    for name, url in manual:
        out.append(f"<li>{html.escape(name)} – <a href='{html.escape(url)}'>przejrzyj ręcznie</a></li>")
    out.append("</ul>")
    return out

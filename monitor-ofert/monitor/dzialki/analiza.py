"""Odsiew, wyliczenia, flagi i ocena działek (rozdział 5 kontekstu)."""
from __future__ import annotations

import re

from monitor.core.offer import Offer
from monitor.dzialki.przeliczniki import ROLNE, ha_przeliczeniowe, ha_rolne, parse_uzytki

# --- odsiew: udział ułamkowy -------------------------------------------------
_SHARE = re.compile(r"udzia[łl]\w*|współwłasno\w*|wspolwlasno\w*|ułamkow\w*|ulamkow\w*"
                    r"|(?<![\d/])\d{1,2}/\d{1,3}(?![\d/])\s*(?:cz\.|częś|czes|udz)", re.I)
_ROAD_AFTER = re.compile(r"^.{0,40}?(drog|dojazd|działk\w* drogow|dzialk\w* drogow)", re.I | re.S)


def is_fractional(text: str) -> bool:
    """Udział ułamkowy zamiast całej działki. „Udział w drodze dojazdowej” nie jest powodem odrzucenia."""
    for m in _SHARE.finditer(text):
        if _ROAD_AFTER.search(text[m.end():m.end() + 60]):
            continue
        return True
    return False


# --- flagi z treści ------------------------------------------------------------
TEXT_FLAGS = {
    "brak dojazdu / dojazd przez prywatną działkę": r"brak (?:dostępu|dojazdu)|bez dojazdu|bez dostępu do drogi|służebno|sluzebno",
    "teren zalewowy / podmokły": r"zalewow|podmok|powodzi",
    "linia energetyczna / gazociąg": r"lini\w* (?:energetyczn|wysokiego napięcia|WN)|gazociąg|gazociag|słup\w* energetyczn",
    "nieuregulowany stan prawny / brak KW": r"brak (?:księgi|ksiegi|KW)|nieuregulowan|bez księgi|zasiedzeni",
    "obciążenia w KW (dział III/IV)": r"dzia[łl]\w* (?:III|IV)\b|hipotek",
}


def text_flags(text: str) -> list[str]:
    return [name for name, rx in TEXT_FLAGS.items() if re.search(rx, text, re.I)]


# --- piecewise linear -------------------------------------------------------
def _interp(x: float, pts: list[tuple[float, float]]) -> float:
    if x <= pts[0][0]:
        return pts[0][1]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x <= x2:
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    return pts[-1][1]


def score_price_per_ha_przel(zl: float) -> float:
    """100 pkt do 60 tys. zł/ha przel., 75 przy 80 tys., 0 od 300 tys."""
    return _interp(zl, [(60_000, 100), (80_000, 75), (150_000, 35), (300_000, 0)])


ZALESIENIE_ZL_HA = 16_059 + 1_377 * 5 + 1_438 * 12  # założenie + pielęgnacja 5 lat + premia 12 lat (stawki 2026)


def analyze(o: Offer, okreg: str, okreg_assumed: bool, cfg: dict) -> None:
    """Uzupełnia o.extra: uzytki, ha_przel, zl_ha_przel, flagi, oceny. Nic nie odrzuca."""
    e = o.extra
    flags: list[str] = list(e.get("flags", []))
    uz = parse_uzytki(o.text)
    e["uzytki"] = [f"{u.symbol}{u.klasa} {u.area_ha:.4f} ha" for u in uz]
    price = o.effective_price
    area = o.area_m2 or (e.get("parcel") or {}).get("area_m2")
    if price and area:
        e["zl_m2"] = round(price / area, 2)
    if o.start_price and o.estimate:
        e["pct_oszacowania"] = round(100 * o.start_price / o.estimate)
    if not uz:
        flags.append("klasy nieznane")
    else:
        hp = ha_przeliczeniowe(uz, okreg)
        e["ha_przel"] = round(hp, 4)
        e["ha_przel_zrodlo"] = f"z opisu ogłoszenia, okręg {okreg}" + (" (założony)" if okreg_assumed else "")
        if price and hp > 0:
            e["zl_ha_przel"] = round(price / hp)
        rolne = ha_rolne(uz)
        total = sum(u.area_ha for u in uz)
        if rolne > 1:
            flags.append("> 1 ha użytków rolnych: ograniczenia KOWR (zgoda / pierwokup)")
        if total and sum(u.area_ha for u in uz if u.symbol == "N") > total / 2:
            flags.append("nieużytki to większość powierzchni")
    if any(u.symbol in ("Ls", "Lz") for u in uz) or re.search(r"\bleśn|\blas\b|zalesion", o.text, re.I):
        flags.append("grunt leśny: pierwokup Lasów Państwowych")
    width = (e.get("parcel") or {}).get("width_m")
    narrow = cfg.get("waski_pas_m", 20)
    if width and width < narrow:
        flags.append(f"wąski pas ({width:.1f} m)")
    orne_ha = sum(u.area_ha for u in uz if u.symbol in ("R", "S"))
    if orne_ha >= 0.1 and (not width or width > 20):
        flags.append("kwalifikuje się do premii zalesieniowej (R/S, ≥ 0,1 ha" + (", szer. > 20 m)" if width else ", szerokość do sprawdzenia)"))
    flags += text_flags(o.text)
    e["flags"] = list(dict.fromkeys(flags))
    e["scores"] = scores(o, uz, e)


NEGATIVE = ("brak dojazdu", "zalewowy", "linia", "nieuregulowany", "obciążenia", "wąski pas", "nieużytki")


def scores(o: Offer, uz, e: dict) -> dict:
    penalty = 12 * sum(any(n in f for n in NEGATIVE) for f in e["flags"])
    out = {}
    zl = e.get("zl_ha_przel")
    if zl:
        best_cls = {u.klasa for u in uz if u.symbol in ("R", "S")}
        bonus = 10 if best_cls & {"IIIa", "IIIb", "III", "IVa", "IVb", "IV"} else 0
        out["krus"] = _clamp(score_price_per_ha_przel(zl) + bonus - penalty)
    orne = [u for u in uz if u.symbol in ("R", "S")]
    if orne and o.effective_price:
        ha = sum(u.area_ha for u in orne)
        size = 100 if 0.5 <= ha <= 1.0 else 70 if 0.3 <= ha <= 2 else 40
        dist = e.get("distance_km")
        near = _interp(dist, [(5, 100), (35, 40)]) if dist is not None else 60
        out["sad"] = _clamp(0.4 * size + 0.3 * near + 0.3 * (out.get("krus") or 50) - penalty)
        zl_ha = o.effective_price / max(ha, 0.01)
        out["zalesienie"] = _clamp(_interp(zl_ha / ZALESIENIE_ZL_HA, [(0.5, 100), (1, 70), (2, 30), (4, 0)]) - penalty)
    if o.effective_price and o.estimate:
        out["inwestycja"] = _clamp(_interp(o.effective_price / o.estimate, [(0.6, 100), (0.8, 80), (1.0, 30), (1.1, 0)]) - penalty)
    return out


def _clamp(x: float) -> int:
    return int(max(0, min(100, round(x))))


def fingerprint(o: Offer) -> str | None:
    """Odcisk do wykrywania tej samej oferty w różnych źródłach."""
    if o.signature:
        return "sig:" + re.sub(r"\W+", "", o.signature.lower())
    pid = (o.extra.get("parcel") or {}).get("id")
    if pid:
        return "dz:" + pid
    if o.area_m2 and o.effective_price:
        loc = re.sub(r"\W+", "", (o.location or o.title).lower().split(",")[0])[:20]
        return f"lap:{loc}|{round(o.area_m2, -2):.0f}|{round(o.effective_price, -3):.0f}"
    return None

"""Wyciąganie liczb z polskich tekstów ogłoszeń: ceny, powierzchnie, daty, sygnatury."""
from __future__ import annotations

import re
import unicodedata

_NUM = r"\d{1,3}(?:[  .]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?"


def to_float(s: str) -> float:
    s = s.replace(" ", " ").strip()
    if re.fullmatch(r"\d{1,3}(?:[ .]\d{3})+(?:,\d+)?", s):
        s = s.replace(" ", "").replace(".", "")
    return float(s.replace(" ", "").replace(",", "."))


def parse_price(text: str) -> float | None:
    m = re.search(rf"({_NUM})\s*(?:zł|zl|pln)\b", text, re.I)
    return to_float(m.group(1)) if m else None


def parse_area_m2(text: str) -> float | None:
    """Powierzchnia w m². Rozpoznaje m², m2, ha, ar."""
    m = re.search(rf"({_NUM})\s*(m²|m2|mkw|m\.\s?kw|ha\b|ar\b|arów\b)", text, re.I)
    if not m:
        return None
    v, unit = to_float(m.group(1)), m.group(2).lower()
    if unit == "ha":
        return v * 10_000
    if unit in ("ar", "arów"):
        return v * 100
    return v


def parse_date(text: str) -> str:
    m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    return "-".join(m.groups()) if m else ""


def parse_signature(text: str) -> str:
    m = re.search(r"\b(G?Km[\s.]*\d+/\d{2,4}|GKm\s*\d+/\d+)\b", text)
    return re.sub(r"\s+", " ", m.group(1)) if m else ""


PARCEL_ID_RE = re.compile(r"\b(\d{6}_\d\.\d{4}\.(?:AR_\d+\.)?\d+(?:/\d+)?)\b")


def parse_parcel_id(text: str) -> str:
    m = PARCEL_ID_RE.search(text)
    return m.group(1) if m else ""


def normalize(text: str, limit: int = 200) -> str:
    t = unicodedata.normalize("NFC", text).lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]

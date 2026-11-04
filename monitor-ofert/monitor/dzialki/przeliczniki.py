"""Hektary przeliczeniowe wg art. 4 ustawy o podatku rolnym (tabela do weryfikacji z aktualnym tekstem)."""
from __future__ import annotations

import re
from dataclasses import dataclass

# klasa -> przeliczniki dla okręgów I, II, III, IV
ORNE = {  # grunty orne i sady
    "I": (1.95, 1.80, 1.65, 1.45), "II": (1.80, 1.65, 1.50, 1.35),
    "IIIa": (1.65, 1.50, 1.40, 1.25), "IIIb": (1.35, 1.25, 1.15, 1.00),
    "IVa": (1.10, 1.00, 0.90, 0.80), "IVb": (0.80, 0.75, 0.65, 0.60),
    "V": (0.35, 0.30, 0.25, 0.20), "VI": (0.20, 0.15, 0.10, 0.05),
}
LAKI = {  # łąki i pastwiska
    "I": (1.75, 1.60, 1.45, 1.35), "II": (1.45, 1.35, 1.25, 1.10), "III": (1.25, 1.15, 1.05, 0.95),
    "IV": (0.75, 0.70, 0.60, 0.55), "V": (0.20, 0.20, 0.15, 0.15), "VI": (0.15, 0.15, 0.10, 0.05),
}
OKREG = {"I": 0, "II": 1, "III": 2, "IV": 3}
STALY_020 = {"Lzr", "W"}  # zadrzewione/zakrzewione grunty rolne, rowy: 0,20 niezależnie od okręgu
ROLNE = {"R", "S", "Ł", "Ps"}


@dataclass
class Uzytek:
    symbol: str      # R, S, Ł, Ps, Ls, Lz, N, B, Br, Lzr, W, dr
    klasa: str       # I, II, IIIa, IIIb, III, IVa, IVb, IV, V, VI, VIz albo ""
    area_ha: float


def factor(symbol: str, klasa: str, okreg: str) -> float:
    if symbol in STALY_020:
        return 0.20
    if symbol not in ROLNE:
        return 0.0
    i = OKREG[okreg]
    if symbol in ("R", "S"):
        k = klasa
        if symbol == "S" and klasa in ("III", "IV"):
            k = klasa + "a"  # sady klasy III i IV jak IIIa i IVa
        k = {"III": "IIIa", "IV": "IVa", "VIz": "VI"}.get(k, k)  # klasa bez podklasy: przyjęto wyższą (do sprawdzenia)
        return ORNE.get(k, (0, 0, 0, 0))[i]
    k = {"IIIa": "III", "IIIb": "III", "IVa": "IV", "IVb": "IV", "VIz": "VI"}.get(klasa, klasa)
    return LAKI.get(k, (0, 0, 0, 0))[i]


def ha_przeliczeniowe(uzytki: list[Uzytek], okreg: str) -> float:
    return sum(u.area_ha * factor(u.symbol, u.klasa, okreg) for u in uzytki)


def ha_rolne(uzytki: list[Uzytek]) -> float:
    return sum(u.area_ha for u in uzytki if u.symbol in ROLNE)


# „RIVa 0,5 ha”, „ŁV – 0,2700 ha”, „PsIV 1200 m2”, „Ls 0,3 ha”, „N 0,22 ha”
_SYM = r"(Lzr|Ps|Ls|Lz|Br|dr|R|S|Ł|L|N|B|W)"
_KL = r"(IIIa|IIIb|IVa|IVb|VIz|III|IV|VI|II|I|V)?"
_AREA = r"(\d+(?:[.,]\d+)?)\s*(ha|m2|m²|a\b|ar)"
UZYTEK_RE = re.compile(rf"(?<![\wąćęłńóśźż]){_SYM}[-\s]?{_KL}(?![\wąćęłńóśźż])\s*[-–:=(]?\s*(?:o\s+pow\.?\s*)?{_AREA}")


def parse_uzytki(text: str) -> list[Uzytek]:
    out = []
    for sym, kl, num, unit in UZYTEK_RE.findall(text):
        if sym == "L":
            sym = "Ł"  # w ogłoszeniach często bez polskiej litery
        v = float(num.replace(",", "."))
        ha = v / 10_000 if unit in ("m2", "m²") else v / 100 if unit in ("a", "ar") else v
        if sym in ROLNE and not kl:
            continue  # użytek rolny bez klasy – nie zgadujemy
        out.append(Uzytek(sym, kl or "", ha))
    return out

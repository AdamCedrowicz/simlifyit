"""Reguły słów z monitor-garazy.ps1: czy fragment tekstu to garaż NA SPRZEDAŻ."""
from __future__ import annotations

import re

GARAGE = re.compile(r"\bgara(?:ż|z)", re.I)
PARKING = re.compile(r"\bmiejsc\w*\s+postojow\w*|\bmiejsc\w*\s+parkingow\w*", re.I)

STRONG = re.compile(
    r"sprzeda|zbyci|zbyw|nabyci|ustanowieni\w*\s+(?:\w+\s+){0,4}?prawa|odrębn\w*\s+własno|odrebn\w*\s+wlasno"
    r"|własnościow|wlasnosciow|licytacj|aukcj|cen\w*\s+wywoławcz|cen\w*\s+wywolawcz", re.I)
WEAK = re.compile(r"przetarg|wykaz|ofert|ogłoszeni|ogloszeni|\bcen[ayę]\b|\bzł\b|\bzl\b", re.I)

RENTAL = re.compile(r"\bnajm|\bnajem|wynaj|dzierżaw|dzierzaw|użyczeni|uzyczeni", re.I)
WORKS = re.compile(
    r"remont|budow|wykonawc|moderniz|dostaw|zamówieni|zamowieni|zaproszeni\w*\s+do\s+złożenia\s+ofert"
    r"|zaproszeni\w*\s+do\s+zlozenia\s+ofert|czyszczeni|wymian|napraw|malowani|konserwacj|montaż|montaz"
    r"|bram\w*\s+garażow|bram\w*\s+garazow", re.I)

PROXIMITY = 300


def _last_pos(rx: re.Pattern, s: str) -> int:
    pos = -1
    for m in rx.finditer(s):
        pos = m.start()
    return pos


def is_sale_hit(text: str, include_parking: bool = False, include_rental: bool = False) -> bool:
    objects = [GARAGE] + ([PARKING] if include_parking else [])
    matches = [m for rx in objects for m in rx.finditer(text)]
    if not matches:
        return False
    strong = STRONG.search(text) is not None
    if not strong and WEAK.search(text) is None:
        return False
    if not strong:
        if WORKS.search(text) or (not include_rental and RENTAL.search(text)):
            return False
    if include_rental:
        return True
    # test bliskości: słowo o najmie bliżej „garaż” niż słowo o sprzedaży = brak trafienia
    for m in matches:
        window = text[max(0, m.start() - PROXIMITY):m.start()]
        rent = _last_pos(RENTAL, window)
        sale = max(_last_pos(STRONG, window), _last_pos(WEAK, window))
        if rent == -1 or sale > rent:
            return True
    return False

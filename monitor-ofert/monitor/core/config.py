"""Wczytywanie plików konfiguracyjnych z katalogu config/."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(name: str):
    with open(CONFIG_DIR / name, encoding="utf-8-sig") as f:
        return json.load(f)


def load_config() -> dict:
    return load_yaml("config.yaml")

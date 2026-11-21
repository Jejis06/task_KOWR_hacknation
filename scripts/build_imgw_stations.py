"""Buduje data/imgw/synop_stations.json – katalog stacji synoptycznych IMGW-PIB ze współrzędnymi.

API `danepubliczne.imgw.pl/api/data/synop` nie podaje współrzędnych, a archiwum dobowe nazywa pliki
3-cyfrowym kodem (np. 2024_330_s.zip). Współrzędne bierzemy z API `api/data/meteo` (kod 9-cyfrowy, ten sam
co w plikach CSV, np. 352160330). Uruchom raz:  uv run --project backend python scripts/build_imgw_stations.py
"""
import json
import re
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/imgw/synop_stations.json"
BASE = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop"
UA = {"User-Agent": "KOWR-HackNation2026-Prototype/0.1"}

year = date.today().year - 1
listing = httpx.get(f"{BASE}/{year}/", headers=UA, timeout=30).text
codes = sorted(set(re.findall(rf"{year}_(\d+)_s\.zip", listing)))
meteo = httpx.get("https://danepubliczne.imgw.pl/api/data/meteo/", headers=UA, timeout=30).json()
by_suffix = {}
for s in meteo:
    k = s.get("kod_stacji") or ""
    if k[:2] in ("34", "35") and s.get("lon") and s.get("lat"):
        by_suffix.setdefault(k[-3:], s)
stations, missing = [], []
for c in codes:
    s = by_suffix.get(c.zfill(3))
    if not s:
        missing.append(c)
        continue
    stations.append({"file_code": c, "station_code": s["kod_stacji"], "name": s["nazwa_stacji"].strip().title(),
                     "lon": float(s["lon"]), "lat": float(s["lat"]),
                     "elevation_m": float(s["wysokosc_npm"]) if s.get("wysokosc_npm") else None})
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({"source": "IMGW-PIB danepubliczne.imgw.pl (api/data/meteo + archiwum dobowe synop)",
                           "built": date.today().isoformat(), "year_listing": year, "stations": stations},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(stations)} stacji zapisanych, bez współrzędnych: {missing}")

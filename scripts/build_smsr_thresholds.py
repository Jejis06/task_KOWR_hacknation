"""Buduje data/knowledge/crops/smsr_thresholds.yaml z wyciągu tabeli SMSR (raw/smsr_progi_www.txt).

Źródło: Rozporządzenie MRiRW z 11.04.2019 (tabela publikowana w SMSR IUNG-PIB). Uruchom:
  uv run --project backend python scripts/build_smsr_thresholds.py
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/knowledge/raw/smsr_progi_www.txt"
OUT = ROOT / "data/knowledge/crops/smsr_thresholds.yaml"
PERIODS = ["03-21..05-20", "04-01..05-31", "04-11..06-10", "04-21..06-20", "05-01..06-30", "05-11..07-10",
           "05-21..07-20", "06-01..07-31", "06-11..08-10", "06-21..08-20", "07-01..08-31", "07-11..09-10",
           "07-21..09-20", "08-01..09-30"]
CATS = ["I", "II", "III", "IV"]

toks = [t.strip().rstrip("|").strip() for t in RAW.read_text(encoding="utf-8").splitlines()]
toks = [t for t in toks if t]
start = toks.index("1.VIII - 30.IX") + 1
groups: dict[str, dict] = {}
i = start
while i < len(toks) and not toks[i].startswith("Wartości klimatycznego"):
    name = toks[i].lower(); i += 1
    cats = {}
    for _ in CATS:
        cat = toks[i]; assert cat in CATS, (name, cat); i += 1
        vals = []
        for _p in PERIODS:
            v = toks[i]; i += 1
            vals.append(None if v in ("x", "-") else int(v))
        cats[cat] = {"not_recommended": all(toks[i - k] == "-" for k in range(1, 15)), "values": vals}
    groups[name] = cats
doc = {
    "source": "Rozporządzenie MRiRW z 11.04.2019 – tabela SMSR IUNG-PIB, susza.iung.pulawy.pl/progi",
    "status": "OK",
    "note": ("Wartości progowe KBW [mm] w okresach sześciodekadowych; KBW < próg = susza (ok. 20% spadku plonu). "
             "null = brak spadku plonów z powodu suszy w tym okresie (x) albo uprawa niewskazana na glebie (-)."),
    "periods": PERIODS,
    "soil_categories": {"I": "bardzo podatna (piaski luźne i słabogliniaste)", "II": "podatna (piaski gliniaste)",
                        "III": "średnio podatna (gliny lekkie, pyły)", "IV": "mało podatna (gliny średnie i ciężkie, iły)"},
    "groups": groups,
}
OUT.write_text("# WYGENEROWANE przez scripts/build_smsr_thresholds.py – nie edytuj ręcznie\n"
               + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=140), encoding="utf-8")
print(f"{OUT}: {len(groups)} grup: {list(groups)}")

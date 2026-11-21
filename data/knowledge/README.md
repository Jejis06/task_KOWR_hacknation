# Lokalna baza wiedzy

Treści, które nie zmieniają się z dnia na dzień (prawo, procedury, dofinansowania, kalendarz upraw), trzymamy lokalnie,
zamiast pobierać je na żywo. Każdy plik YAML ma `meta.snapshot_date`, a każdy wpis ma `status`
(`OK` | `DO_WERYFIKACJI` | `SZACUNEK`) i `sources`. Backend serwuje je pod `/api/knowledge/{kolekcja}`.

| Kolekcja | Plik |
|---|---|
| crops | `crops/crops.yaml` |
| legal_pl | `legal_pl/prawo_wodne.yaml` |
| procedures | `procedures/procedures.yaml` |
| measures | `procedures/retention_measures.yaml` |
| funding | `funding/programs.yaml` |
| eu_law | `eu_law/eu_law.yaml` |

`raw/` zawiera dokumenty źródłowe z `sources.yaml`. W repo trzymamy `*.txt` (tekst do grep) i `manifest.json`.
PDF-y odtwarza: `make knowledge`. Pełny research z oznaczeniami: `baza_wiedzy_woda.md`.
Informacja orientacyjna – nie stanowi porady prawnej.

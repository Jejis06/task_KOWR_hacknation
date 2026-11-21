"""Konektory DO ZAIMPLEMENTOWANIA przez zespół DATA (prompt: prompts/AGENT_A_DATA.md).

Każda klasa ma w docstringu: źródło, endpoint, co zwrócić (model z contracts) i pułapki.
Implementując: przenieś klasę do własnego pliku `connectors/<key>.py`, dziedzicz po `Connector`
(nie `StubConnector`), zaktualizuj import w `connectors/registry.py` i tabelę w AGENTS.md §4.
"""
from __future__ import annotations

from app.connectors.base import StubConnector







class YieldsConnector(StubConnector):
    """Plony historyczne → YieldInfo.
    UWAGA: publicznych plonów per pole w Polsce NIE MA. Dwa źródła:
    1) GUS BDL API https://bdl.stat.gov.pl/api/v1 – plony (dt/ha) wg upraw, powiat/województwo, lata
       (bez klucza: limit zapytań; opcjonalny X-ClientId). Mapuj klucz uprawy → zmienna BDL.
    2) Proxy per działka: szczytowe NDVI w sezonie z VegetationConnector → indeks względny (rok / mediana 10 lat).
    Komunikuj jasno: „plony urzędowe dla powiatu, nie dla Twojego pola”.
    """
    key = "yields"; title = "Plony historyczne"; category = "derived"; live_ttl_s = 30 * 24 * 3600
    uses_crop = True





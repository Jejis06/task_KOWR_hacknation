"""Bloki profilu liczone z lokalnej bazy wiedzy + faktów o działce (zespół PRODUCT).

DO ZAIMPLEMENTOWANIA (prompt: prompts/AGENT_B_PRODUCT.md):
- CropCalendarConnector → CropCalendarInfo: na podstawie crops.yaml i ctx.as_of – czy uprawa jest w sezonie,
  aktualna faza (Kc), okresy krytyczne, czy to dobry termin siewu, ostrzeżenia
  („listopad: nie siej kukurydzy – okres wegetacji 120–150 dni, siew IV–V”), sugestie upraw na teraz.
- LegalContextConnector → LegalContextInfo: reguły z legal_pl + procedures + measures, parametryzowane faktami
  z innych bloków (strefa powodziowa, Natura 2000, odległość do cieku, głębokość wód) – dlatego jest
  liczony w services/profile.py PO blokach danych (depends_on).
"""
from __future__ import annotations

from typing import ClassVar

from app.connectors.base import StubConnector


class CropCalendarConnector(StubConnector):
    key = "crop_calendar"; title = "Kalendarz uprawy i okres wegetacji"; category = "knowledge"
    uses_crop = True
    live_ttl_s = 24 * 3600


class LegalContextConnector(StubConnector):
    key = "legal_context"; title = "Pozwolenia, procedury i dofinansowania"; category = "knowledge"
    uses_crop = True
    depends_on: ClassVar[tuple[str, ...]] = ("hydrology", "protected_areas", "terrain")

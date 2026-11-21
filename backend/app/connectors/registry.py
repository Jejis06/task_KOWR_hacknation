"""Rejestr bloków profilu działki. Kolejność = kolejność wyświetlania w UI.

Dodając konektor: zaimportuj klasę i dopisz instancję do BLOCKS. Klucz musi być unikalny
i zgodny z tabelą w AGENTS.md §4 oraz z `frontend/src/api/types.ts` (BlockKey).
"""
from __future__ import annotations

from app.connectors.base import Connector
from app.connectors.stubs import (DroughtConnector, HydrologyConnector, LandCoverConnector,
                                  ProtectedAreasConnector,
                                  VegetationConnector, YieldsConnector)
from app.connectors.soil import SoilConnector
from app.connectors.terrain import TerrainConnector
from app.connectors.weather import WeatherForecastConnector, WeatherHistoryConnector
from app.knowledge.blocks import CropCalendarConnector, LegalContextConnector

BLOCKS: dict[str, Connector] = {c.key: c for c in [
    WeatherHistoryConnector(),
    WeatherForecastConnector(),
    DroughtConnector(),
    SoilConnector(),
    TerrainConnector(),
    HydrologyConnector(),
    VegetationConnector(),
    LandCoverConnector(),
    YieldsConnector(),
    ProtectedAreasConnector(),
    CropCalendarConnector(),
    LegalContextConnector(),
]}

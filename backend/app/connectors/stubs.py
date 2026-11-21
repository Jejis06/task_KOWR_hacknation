"""Konektory DO ZAIMPLEMENTOWANIA przez zespół DATA (prompt: prompts/AGENT_A_DATA.md).

Każda klasa ma w docstringu: źródło, endpoint, co zwrócić (model z contracts) i pułapki.
Implementując: przenieś klasę do własnego pliku `connectors/<key>.py`, dziedzicz po `Connector`
(nie `StubConnector`), zaktualizuj import w `connectors/registry.py` i tabelę w AGENTS.md §4.
"""
from __future__ import annotations

from app.connectors.base import StubConnector





class VegetationConnector(StubConnector):
    """Sentinel-2 → VegetationInfo (NDVI/NDMI, 10 lat, bez konta).
    STAC Earth Search: https://earth-search.aws.element84.com/v1  (kolekcja sentinel-2-l2a, COG na S3).
    Czytaj tylko okno działki z COG (HTTP range, rasterio/rio-tiler) – pasma B04, B08, B11, SCL.
    Maska chmur SCL (klasy 4,5 = ok). Seria: ≤1 czysta scena / miesiąc / rok w IV–X (budżet czasu!).
    latest = najnowsza czysta scena ≤ as_of (podaj latest_age_days); baseline = mediana NDVI z ±15 dni DOY z 10 lat.
    Poza sezonem (XI–III) → status not_applicable dla `latest`, ale zwróć serię historyczną.
    Licencja: Copernicus Sentinel data – darmowe, wymagane przypisanie.
    """
    key = "vegetation"; title = "Stan roślinności (satelita)"; category = "satellite"; live_ttl_s = 24 * 3600
    uses_crop = False



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


class LandCoverConnector(StubConnector):
    """Pokrycie terenu w granicach działki → LandCoverInfo (działka ≠ pole!).
    ESA WorldCover 10 m (COG, publiczny S3, CC BY 4.0):
      https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N51E021_Map.tif
    Alternatywnie BDOT10k / EGiB klasoużytki. Wynik maskuje analizy (NDVI tylko z gruntów rolnych).
    """
    key = "land_cover"; title = "Użytkowanie terenu"; category = "spatial"; live_ttl_s = 30 * 24 * 3600



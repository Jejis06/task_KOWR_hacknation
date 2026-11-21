"""Konektory DO ZAIMPLEMENTOWANIA przez zespół DATA (prompt: prompts/AGENT_A_DATA.md).

Każda klasa ma w docstringu: źródło, endpoint, co zwrócić (model z contracts) i pułapki.
Implementując: przenieś klasę do własnego pliku `connectors/<key>.py`, dziedzicz po `Connector`
(nie `StubConnector`), zaktualizuj import w `connectors/registry.py` i tabelę w AGENTS.md §4.
"""
from __future__ import annotations

from app.connectors.base import StubConnector




class HydrologyConnector(StubConnector):
    """Hydrologia → HydrologyInfo.
    - Cieki/rowy/zbiorniki w promieniu ~1 km: MPHP 1:10 000 (Wody Polskie, WMS/WFS – sprawdź aktualny URL,
      wody.isok.gov.pl/gpservices/... zwracał 401) albo BDOT10k (SWRS/PTWP) z geoportalu.
    - Strefy zagrożenia powodziowego ISOK (0,2% / 1% / 10%): WMS GetFeatureInfo
      https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_MZPMRP_WMS
    - PIG-PIB: CBDH otwory (WFS) https://cbdgmapa.pgi.gov.pl/arcgis/services/hydrogeologia/cbdh_otwory/MapServer/WFSServer
      → najbliższe otwory: głębokość, zwierciadło, wydajność; MHP 1:50 000 – głębokość do 1. poziomu wodonośnego; GZWP.
    - Właściwy Zarząd Zlewni / Nadzór Wodny (do procedur) – z JCWP/zlewni.
    """
    key = "hydrology"; title = "Wody powierzchniowe i podziemne"; category = "hydro"; live_ttl_s = 30 * 24 * 3600


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


class DroughtConnector(StubConnector):
    """Susza historyczna i bieżąca → DroughtHistory.
    - SMSR IUNG-PIB https://susza.iung.pulawy.pl/ – zagrożenie suszą per gmina/uprawa/kategoria gleby,
      okresy 6-dekadowe IV–IX, archiwum od 2008. Brak oficjalnego API – zbadaj endpointy mapy (XHR) i licencję;
      jeśli niedostępne → local_snapshot dla zebranych gmin + jawny komunikat.
    - EDO Copernicus WMS (CDI, SMA, fAPAR anomaly) z parametrem TIME:
      https://drought.emergency.copernicus.eu/api/wms  (GetFeatureInfo w punkcie, daty z 10 lat).
    - drought_years: lata, w których min_cwb_60d (weather_history) < próg dla uprawy/gleby – wylicz w services.
    """
    key = "drought"; title = "Susza – teraz i w historii"; category = "meteo"; live_ttl_s = 24 * 3600
    uses_crop = True


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


class ProtectedAreasConnector(StubConnector):
    """Formy ochrony przyrody → ProtectedAreasInfo (wpływa na procedury: RDOŚ, ocena oddziaływania).
    GDOŚ WMS/WFS: https://sdi.gdos.gov.pl/wms (Natura 2000 OSO/SOO, rezerwaty, parki narodowe/krajobrazowe, OChK).
    Sprawdź przecięcie geometrii działki (nie tylko centroid).
    """
    key = "protected_areas"; title = "Obszary chronione"; category = "spatial"; live_ttl_s = 30 * 24 * 3600

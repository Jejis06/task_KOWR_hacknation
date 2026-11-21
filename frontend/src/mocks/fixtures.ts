// Dane przykładowe zgodne z kontraktem – UI działa bez backendu (VITE_USE_MOCKS=true).
import type { BlockInfo, CropItem, DataBlock, ParcelRef } from "../api/types";

export const mockParcel: ParcelRef = {
  id: "146505_8.0116.5",
  teryt_unit: "146505_8",
  region_code: "0116",
  parcel_number: "5",
  voivodeship: "mazowieckie",
  county: "powiat Warszawa",
  commune: "Warszawa (miasto)",
  region_name: "1-01-16",
  geometry: {
    type: "Polygon",
    coordinates: [[[20.99998, 52.19988], [21.00041, 52.19949], [20.99996, 52.20106], [20.99966, 52.201], [20.99998, 52.19988]]],
  },
  centroid: [20.99995, 52.2002],
  bbox: [20.99966, 52.19949, 21.00041, 52.20106],
  area_ha: 0.42,
};

export const mockBlocks: BlockInfo[] = [
  { key: "weather_history", title: "Opady i parowanie – 10 lat", category: "meteo", implemented: true },
  { key: "weather_forecast", title: "Prognoza pogody (16 dni)", category: "meteo", implemented: true },
  { key: "drought", title: "Susza – teraz i w historii", category: "meteo", implemented: true },
  { key: "soil", title: "Gleba", category: "soil", implemented: true },
  { key: "terrain", title: "Ukształtowanie terenu", category: "spatial", implemented: true },
  { key: "hydrology", title: "Wody powierzchniowe i podziemne", category: "hydro", implemented: true },
  { key: "vegetation", title: "Stan roślinności (satelita)", category: "satellite", implemented: true },
  { key: "land_cover", title: "Użytkowanie terenu", category: "spatial", implemented: true },
  { key: "yields", title: "Plony historyczne", category: "derived", implemented: true },
  { key: "protected_areas", title: "Obszary chronione", category: "spatial", implemented: true },
  { key: "crop_calendar", title: "Kalendarz uprawy i okres wegetacji", category: "knowledge", implemented: false },
  { key: "legal_context", title: "Pozwolenia, procedury i dofinansowania", category: "knowledge", implemented: false },
];

export const mockCrops: CropItem[] = [
  { id: "pszenica_ozima", name_pl: "Pszenica ozima", type: "ozima", sowing: "09-15..10-20", harvest: "07-20..08-20" },
  { id: "kukurydza_ziarno", name_pl: "Kukurydza na ziarno", type: "jara", sowing: "04-20..05-15", harvest: "09-25..11-15" },
  { id: "ziemniak", name_pl: "Ziemniak", type: "jara", sowing: "04-05..05-10", harvest: "08-15..10-10" },
];

export function mockBlock(key: string): DataBlock {
  if (key in realSamples) return realSamples[key];
  const info = mockBlocks.find((b) => b.key === key);
  const now = new Date().toISOString();
  if (key === "weather_history") {
    return {
      key, title: info!.title, status: "ok",
      data: {
        provider: "nasa-power", grid_resolution_note: "MOCK", start: "2016-11-01", end: "2026-11-20",
        daily: { dates: [], precip_mm: [], tmax_c: [], tmin_c: [], et0_mm: [] },
        monthly_climatology: [], seasons: [
          { year: 2024, precip_apr_sep_mm: 310, et0_apr_sep_mm: 560, cwb_apr_sep_mm: -250, longest_dry_spell_days: 19, min_cwb_60d_mm: -142 },
        ],
        last_30d_precip_mm: 22.1, last_30d_precip_normal_mm: 38.4, cwb_60d_mm: -35, cwb_60d_normal_mm: -10,
      },
      provenance: [{ source_name: "MOCK", retrieved_at: now, mode: "local_snapshot" }],
      uncertainty: ["Dane przykładowe (tryb mock)."], messages: [], elapsed_ms: 5,
    };
  }
  return {
    key, title: info?.title ?? key, status: info?.implemented ? "no_data" : "not_implemented", data: null,
    provenance: [], uncertainty: [], messages: ["Tryb mock"], elapsed_ms: 1,
  };
}

// Prawdziwe próbki bloków zespołu DATA (A) – działka 302504_5.0019.52/16 (Środa Wlkp.), data 2024-07-15,
// pszenica ozima; skrócone (serie, geometrie). Wygenerowane z /api/parcel/profile 2026-11-21.
export const realSamples: Record<string, DataBlock> = {
 "weather_history": {
  "key": "weather_history",
  "title": "Opady i parowanie – 10 lat",
  "status": "ok",
  "data": {
   "provider": "nasa-power",
   "grid_resolution_note": "siatka MERRA-2 ok. 50 km (zgrubna!)",
   "start": "2014-07-01",
   "end": "2024-07-15",
   "daily": {
    "dates": [],
    "precip_mm": [],
    "tmax_c": [],
    "tmin_c": [],
    "et0_mm": []
   },
   "monthly_climatology": [
    {
     "month": 4,
     "precip_mean_mm": 36.7,
     "et0_mean_mm": 65.9,
     "cwb_mean_mm": -29.2
    },
    {
     "month": 5,
     "precip_mean_mm": 56.0,
     "et0_mean_mm": 101.6,
     "cwb_mean_mm": -45.6
    },
    {
     "month": 6,
     "precip_mean_mm": 62.6,
     "et0_mean_mm": 127.9,
     "cwb_mean_mm": -65.3
    },
    {
     "month": 7,
     "precip_mean_mm": 72.4,
     "et0_mean_mm": 135.3,
     "cwb_mean_mm": -62.9
    },
    {
     "month": 8,
     "precip_mean_mm": 65.2,
     "et0_mean_mm": 119.1,
     "cwb_mean_mm": -53.9
    },
    {
     "month": 9,
     "precip_mean_mm": 47.1,
     "et0_mean_mm": 75.5,
     "cwb_mean_mm": -28.4
    }
   ],
   "seasons": [
    {
     "year": 2021,
     "precip_apr_sep_mm": 421.2,
     "et0_apr_sep_mm": 544.9,
     "cwb_apr_sep_mm": -123.7,
     "longest_dry_spell_days": 10,
     "min_cwb_60d_mm": -104.6
    },
    {
     "year": 2022,
     "precip_apr_sep_mm": 349.5,
     "et0_apr_sep_mm": 648.2,
     "cwb_apr_sep_mm": -298.7,
     "longest_dry_spell_days": 24,
     "min_cwb_60d_mm": -183.6
    },
    {
     "year": 2023,
     "precip_apr_sep_mm": 338.1,
     "et0_apr_sep_mm": 625.1,
     "cwb_apr_sep_mm": -287.0,
     "longest_dry_spell_days": 20,
     "min_cwb_60d_mm": -184.9
    }
   ],
   "last_30d_precip_mm": 126.7,
   "last_30d_precip_normal_mm": 72.0,
   "cwb_60d_mm": -7.6,
   "cwb_60d_normal_mm": -131.7,
   "station_check": {
    "seasons_apr_sep": [
     {
      "year": 2021,
      "reanalysis_mm": 421.0,
      "station_mm": 317.0
     },
     {
      "year": 2022,
      "reanalysis_mm": 350.0,
      "station_mm": 229.0
     },
     {
      "year": 2023,
      "reanalysis_mm": 338.0,
      "station_mm": 326.0
     }
    ],
    "season_bias_pct": 19.0,
    "station_last_30d_precip_mm": 95.9,
    "mean_abs_season_diff_mm": 60.0,
    "station": "Poznań-Ławica",
    "station_code": "352160330",
    "distance_km": 37.3
   }
  },
  "provenance": [
   {
    "source_name": "NASA POWER (MERRA-2)",
    "source_url": "https://power.larc.nasa.gov/api/temporal/daily/point",
    "licence": "Domena publiczna (NASA)",
    "retrieved_at": "2026-11-21T13:56:20.648693Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": "2024-07-15",
    "notes": null
   },
   {
    "source_name": "IMGW-PIB – dane dobowe stacji synoptycznej Poznań-Ławica",
    "source_url": "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_meteorologiczne/dobowe/synop",
    "licence": "Dane publiczne IMGW-PIB – „Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – PIB”",
    "retrieved_at": "2026-11-21T13:56:21.030819Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "37.3 km od działki; walidacja opadu reanalizy"
   }
  ],
  "uncertainty": [
   "Dane z reanalizy (siatka MERRA-2 ok. 50 km (zgrubna!)), nie z pomiaru na działce – lokalne burze mogą być pominięte.",
   "Norma = średnia z dostępnych lat w oknie 10-letnim, nie klimatologia 30-letnia.",
   "Opad z reanalizy różni się od pomiarów stacji IMGW Poznań-Ławica (37.3 km) średnio o +19% w sezonach IV–IX – traktuj sumy opadów ostrożnie."
  ],
  "messages": [
   "Open-Meteo Historical Weather API (ERA5/ERA5-Land, ECMWF Copernicus): limit zapytań (429) – przełączono na źródło zapasowe."
  ],
  "elapsed_ms": 0
 },
 "drought": {
  "key": "drought",
  "title": "Susza – teraz i w historii",
  "status": "ok",
  "data": {
   "current": [
    {
     "source": "SMSR IUNG",
     "date": "2024-07-10",
     "value": "-",
     "class_label": "brak suszy (kryterium nieprzekroczone)",
     "level": "commune"
    },
    {
     "source": "computed",
     "date": "2024-07-10",
     "value": -93.7,
     "class_label": "brak suszy – KBW -94 mm, próg -186 mm",
     "level": "parcel"
    },
    {
     "source": "EDO CDI",
     "date": "2024-07-11",
     "value": "brak suszy rolniczej",
     "class_label": "brak suszy rolniczej",
     "level": "pixel"
    },
    {
     "source": "EDO SMA",
     "date": "2024-07-11",
     "value": 0.0,
     "class_label": "−1 – 1 (norma)",
     "level": "pixel"
    }
   ],
   "history": [
    {
     "source": "SMSR IUNG",
     "date": "2022-08-10",
     "value": "brak suszy",
     "class_label": "brak suszy",
     "level": "commune"
    },
    {
     "source": "EDO CDI",
     "date": "2023-07-01",
     "value": "ostrzeżenie (Warning)",
     "class_label": "ostrzeżenie (Warning)",
     "level": "pixel"
    },
    {
     "source": "computed",
     "date": "2023-07-20",
     "value": -189.2,
     "class_label": "brak suszy (najgorszy okres 07: KBW -189 mm, próg -201 mm)",
     "level": "parcel"
    },
    {
     "source": "SMSR IUNG",
     "date": "2023-08-10",
     "value": "5/9 okresów z suszą",
     "class_label": "zagrożenie suszą",
     "level": "commune"
    },
    {
     "source": "computed",
     "date": "2024-05-20",
     "value": -92.9,
     "class_label": "brak suszy (najgorszy okres 01: KBW -93 mm, próg -150 mm)",
     "level": "parcel"
    },
    {
     "source": "SMSR IUNG",
     "date": "2024-07-10",
     "value": "brak suszy",
     "class_label": "brak suszy",
     "level": "commune"
    }
   ],
   "drought_years": [
    2018,
    2019,
    2020,
    2023
   ],
   "drought_years_smsr": [
    2020,
    2023
   ],
   "drought_years_computed": [
    2018,
    2019
   ],
   "crop_group": "zboża ozime",
   "soil_category": 2,
   "commune_teryt": "3025043",
   "commune_name": "Środa Wielkopolska",
   "periods": [
    {
     "year": 2024,
     "period": 1,
     "start": "2024-03-21",
     "end": "2024-05-20",
     "kbw_mm": -92.9,
     "threshold_mm": -150,
     "drought": false,
     "source": "computed"
    },
    {
     "year": 2024,
     "period": 1,
     "start": "2024-03-21",
     "end": "2024-05-20",
     "drought": false,
     "source": "smsr",
     "commune_area_share_pct": 6.49
    },
    {
     "year": 2024,
     "period": 2,
     "start": "2024-04-01",
     "end": "2024-05-31",
     "kbw_mm": -92.2,
     "threshold_mm": -153,
     "drought": false,
     "source": "computed"
    },
    {
     "year": 2024,
     "period": 2,
     "start": "2024-04-01",
     "end": "2024-05-31",
     "drought": false,
     "source": "smsr",
     "commune_area_share_pct": 1.68
    },
    {
     "year": 2024,
     "period": 3,
     "start": "2024-04-11",
     "end": "2024-06-10",
     "kbw_mm": -79.7,
     "threshold_mm": -158,
     "drought": false,
     "source": "computed"
    },
    {
     "year": 2024,
     "period": 3,
     "start": "2024-04-11",
     "end": "2024-06-10",
     "drought": false,
     "source": "smsr",
     "commune_area_share_pct": 0.04
    }
   ]
  },
  "provenance": [
   {
    "source_name": "IUNG-PIB SMSR – zagrożenie suszą w gminie Środa Wielkopolska",
    "source_url": "https://susza.iung.pulawy.pl/wykazy/2024,3025043/",
    "licence": "IUNG-PIB SMSR – informacja publiczna (susza.iung.pulawy.pl), z podaniem źródła",
    "retrieved_at": "2026-11-21T13:34:25.256288Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "lata 2020–2024, kategoria gleby II, grupa „zboża ozime”"
   },
   {
    "source_name": "Klimatyczny bilans wodny (KBW) policzony dla działki metodą SMSR",
    "source_url": null,
    "licence": "obliczenia własne; progi: rozporządzenie MRiRW 11.04.2019",
    "retrieved_at": "2026-11-21T13:34:25.276987Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": "2024-07-15",
    "notes": "dane meteo: nasa-power"
   },
   {
    "source_name": "Copernicus EDO – Combined Drought Indicator i anomalia wilgotności gleby",
    "source_url": "https://drought.emergency.copernicus.eu/api/wms",
    "licence": "Copernicus Emergency Management Service – EDO (JRC), bezpłatnie z przypisaniem źródła",
    "retrieved_at": "2026-11-21T13:34:25.277196Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "CDI v4.1 (cdiad), SMA (smang); dekady; siatka ok. 5 km"
   }
  ],
  "uncertainty": [
   "SMSR publikuje tabele dla gmin od 2020 r. – wcześniejsze lata oceniamy wyłącznie z bilansu wodnego policzonego dla działki.",
   "KBW dla działki liczymy z reanalizy (ERA5 lub NASA POWER), a SMSR – z pomiarów stacji IMGW; wyniki są zbliżone, ale mogą się różnić o kilkadziesiąt mm.",
   "EDO to siatka europejska (ok. 5 km) – opisuje okolicę, nie pojedyncze pole. W historii pokazujemy tylko daty, w których CDI wskazywał suszę (21.05, 1.07, 11.08)."
  ],
  "messages": [],
  "elapsed_ms": 0
 },
 "soil": {
  "key": "soil",
  "title": "Gleba",
  "status": "ok",
  "data": {
   "agri_complex": "pszenny bardzo dobry (1)",
   "soil_type": "czarne ziemie (D)",
   "texture_class": "piasek gliniasty mocny na glina lekka",
   "drought_susceptibility": "kategoria II – podatna na suszę (gleby lekkie)",
   "bonitation_classes": [],
   "clay_pct": null,
   "sand_pct": null,
   "silt_pct": null,
   "soc_g_kg": null,
   "awc_mm": 150.0,
   "source_used": "iung_katgl+mgr",
   "drought_category": 2,
   "drought_category_shares_pct": {
    "2": 100.0
   },
   "agri_complex_code": "1",
   "agri_complex_shares_pct": {
    "1": 100.0
   },
   "texture_profile": [
    "pgm",
    "gl"
   ],
   "samples": [
    {
     "lon": 17.252492,
     "lat": 52.199065,
     "drought_category": 2,
     "agri_complex": "1",
     "soil_type": "D",
     "texture": [
      "pgm",
      "gl"
     ],
     "flood_terrain": false
    },
    {
     "lon": 17.249015,
     "lat": 52.199683,
     "drought_category": 2,
     "agri_complex": "1",
     "soil_type": "D",
     "texture": [
      "pgm",
      "gl"
     ],
     "flood_terrain": false
    }
   ]
  },
  "provenance": [
   {
    "source_name": "IUNG-PIB – Mapa kategorii podatności gleb na suszę (SMSR)",
    "source_url": "https://sgeo.iung.pl/geoserver/wms?layers=Susza:katgl_landuse2024",
    "licence": "IUNG-PIB – udostępnione publicznie w SMSR (susza.iung.pulawy.pl); przypisanie źródła",
    "retrieved_at": "2026-11-21T13:34:20.288672Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "GetFeatureInfo w 5 punktach działki"
   },
   {
    "source_name": "GUGiK – Mapa glebowo-rolnicza 1:5000 (IUNG)",
    "source_url": "https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer",
    "licence": "Dane PZGiK – bezpłatne (art. 40a Prawa geodezyjnego i kartograficznego)",
    "retrieved_at": "2026-11-21T13:34:20.288784Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "warstwa KONTURY_GLEBOWE"
   }
  ],
  "uncertainty": [
   "Zapas wody dostępnej ≈ 150 mm to typowa wartość dla kategorii gleby (środek przedziału WOD wg IUNG), a nie pomiar na Twoim polu – SZACUNEK.",
   "Mapa glebowo-rolnicza powstała głównie w latach 60.–80. XX w. – stan gleby mógł się zmienić (erozja, melioracje, materia organiczna)."
  ],
  "messages": [
   "SoilGrids niedostępne (ReadTimeout)."
  ],
  "elapsed_ms": 0
 },
 "terrain": {
  "key": "terrain",
  "title": "Ukształtowanie terenu",
  "status": "ok",
  "data": {
   "elevation_mean_m": 84.9,
   "elevation_min_m": 83.8,
   "elevation_max_m": 86.0,
   "slope_mean_deg": 0.5,
   "slope_max_deg": 1.4,
   "aspect_dominant": null,
   "position": "flat",
   "position_label_pl": "teren płaski",
   "tpi_m": 0.05,
   "twi_mean": 8.6,
   "depressions_geojson": {
    "type": "FeatureCollection",
    "features": [
     {
      "type": "Feature",
      "geometry": {
       "type": "Polygon",
       "coordinates": [
        [
         [
          17.25048,
          52.19975
         ],
         [
          17.25049,
          52.19951
         ],
         [
          17.25125,
          52.19952
         ],
         [
          17.25124,
          52.19964
         ],
         [
          17.25048,
          52.19975
         ],
         [
          17.25048,
          52.19975
         ]
        ]
       ]
      },
      "properties": {
       "area_m2": 1014,
       "max_depth_m": 0.2,
       "volume_m3": 118,
       "touches_parcel": true
      }
     },
     {
      "type": "Feature",
      "geometry": {
       "type": "Polygon",
       "coordinates": [
        [
         [
          17.25197,
          52.20059
         ],
         [
          17.25198,
          52.20035
         ],
         [
          17.25217,
          52.20035
         ],
         [
          17.25217,
          52.20024
         ],
         [
          17.25274,
          52.20025
         ],
         [
          17.25273,
          52.20048
         ],
         [
          17.25216,
          52.20047
         ],
         [
          17.25216,
          52.20059
         ],
         [
          17.25197,
          52.20059
         ]
        ]
       ]
      },
      "properties": {
       "area_m2": 1352,
       "max_depth_m": 1.4,
       "volume_m3": 1758,
       "touches_parcel": false
      }
     }
    ]
   },
   "flow_lines_geojson": {
    "type": "FeatureCollection",
    "features": [
     {
      "type": "Feature",
      "geometry": {
       "type": "LineString",
       "coordinates": [
        [
         17.25497,
         52.19917
        ],
        [
         17.25556,
         52.19871
        ],
        [
         17.2552,
         52.19824
        ],
        [
         17.25539,
         52.19812
        ],
        [
         17.2554,
         52.19789
        ],
        [
         17.25522,
         52.19777
        ]
       ]
      },
      "properties": {
       "length_m": 262,
       "catchment_ha": 22.17,
       "crosses_parcel": true
      }
     },
     {
      "type": "Feature",
      "geometry": {
       "type": "LineString",
       "coordinates": [
        [
         17.25511,
         52.20057
        ],
        [
         17.2553,
         52.20046
        ],
        [
         17.25533,
         52.19988
        ],
        [
         17.25496,
         52.19952
        ],
        [
         17.25497,
         52.19917
        ]
       ]
      },
      "properties": {
       "length_m": 172,
       "catchment_ha": 18.03,
       "crosses_parcel": true
      }
     }
    ]
   },
   "dem_resolution_m": 13.0
  },
  "provenance": [
   {
    "source_name": "GUGiK – Numeryczny Model Terenu (NMT, ALS), usługa GetHByPointList",
    "source_url": "https://services.gugik.gov.pl/nmt/",
    "licence": "Dane PZGiK – bezpłatne, dowolny cel (art. 40a Prawa geodezyjnego i kartograficznego)",
    "retrieved_at": "2026-11-21T13:57:57.029967Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "siatka 67×91, krok 13 m, bufor 300 m"
   }
  ],
  "uncertainty": [
   "Wysokości z NMT GUGiK (skaning laserowy) próbkowane co 13 m – drobne formy (bruzdy, rowy węższe niż 13 m) mogą być niewidoczne.",
   "Zagłębienia i linie spływu wyznaczone z samej rzeźby terenu – nie uwzględniają drenażu, przepustów ani rowów pod drogami.",
   "Na działce i w jej pobliżu (300 m): 1 zagłębień bezodpływowych stykających się z działką, 5 głównych linii spływu przecinających działkę."
  ],
  "messages": [],
  "elapsed_ms": 5794
 },
 "hydrology": {
  "key": "hydrology",
  "title": "Wody powierzchniowe i podziemne",
  "status": "ok",
  "data": {
   "nearest_water": [
    {
     "kind": "pond",
     "name": "staw / oczko",
     "distance_m": 59.0,
     "geometry": null
    },
    {
     "kind": "ditch",
     "name": "rów melioracyjny",
     "distance_m": 243.0,
     "geometry": null
    },
    {
     "kind": "pond",
     "name": "staw / oczko",
     "distance_m": 278.0,
     "geometry": null
    }
   ],
   "in_flood_zone": null,
   "flood_zone_checked": true,
   "catchment_name": "region wodny Warty (dorzecze: Odra)",
   "jcwp_code": null,
   "groundwater_depth_m": null,
   "gzwp": "GZWP nr 143 „Subzbiornik Inowrocław - Gniezno” (porowy, śr. głębokość ok. 120 m)",
   "nearest_boreholes": [
    {
     "name": "5080026-RSP-1",
     "distance_m": 189,
     "depth_m": 63.0,
     "year": "1964",
     "type": "Otwór",
     "purpose": "Eksploatacja",
     "locality": "Strzeszki",
     "decommissioned": false,
     "lon": 17.245952,
     "lat": 52.198281
    },
    {
     "name": "5090185-WODOCIĄG-1",
     "distance_m": 370,
     "depth_m": 132.5,
     "year": "1969",
     "type": "Otwór",
     "purpose": "Eksploatacja",
     "locality": "Chwałkowo",
     "decommissioned": false,
     "lon": 17.249559,
     "lat": 52.195501
    }
   ],
   "water_management_board": "PGW Wody Polskie – RZGW w Poznaniu (wg regionu wodnego; właściwy Zarząd Zlewni i Nadzór Wodny sprawdź na wody.gov.pl)",
   "in_flood_hazard_area": false,
   "in_groundwater_flood_area": false,
   "jcwpd_code": "PLGW600061"
  },
  "provenance": [
   {
    "source_name": "ISOK / PGW Wody Polskie – mapy zagrożenia powodziowego (MZP)",
    "source_url": "https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_MZPMRP_WMS",
    "licence": "Dane publiczne PGW Wody Polskie (ISOK) – bezpłatne ponowne wykorzystanie",
    "retrieved_at": "2026-11-21T13:57:51.995983Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "warstwa NZ.Fluvial (cykl MZP 2022), scenariusze Q10%, Q1%, Q0,2%; GetMap z własnym SLD"
   },
   {
    "source_name": "BDOT10k – sieć wodna (kopia w usłudze PIG-PIB)",
    "source_url": "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/mapa_topo/bdot_10k/MapServer",
    "licence": "BDOT10k (PZGiK) – bezpłatne; kopia udostępniana przez PIG-PIB",
    "retrieved_at": "2026-11-21T13:57:51.996013Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "promień 1000 m"
   },
   {
    "source_name": "PIG-PIB – Centralna Baza Danych Hydrogeologicznych (CBDH)",
    "source_url": "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/cbdh_otwory/MapServer",
    "licence": "PIG-PIB – dane publiczne, bezpłatne do ponownego wykorzystania z podaniem źródła",
    "retrieved_at": "2026-11-21T13:57:51.996026Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "promień 3000 m"
   },
   {
    "source_name": "PIG-PIB – Główne Zbiorniki Wód Podziemnych (GZWP)",
    "source_url": "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/gzwp/MapServer",
    "licence": "PIG-PIB – dane publiczne, bezpłatne do ponownego wykorzystania z podaniem źródła",
    "retrieved_at": "2026-11-21T13:57:51.996037Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": null
   },
   {
    "source_name": "PIG-PIB – Jednolite Części Wód Podziemnych (JCWPd 2022–2027)",
    "source_url": "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/jcwpd/MapServer",
    "licence": "PIG-PIB – dane publiczne, bezpłatne do ponownego wykorzystania z podaniem źródła",
    "retrieved_at": "2026-11-21T13:57:51.996059Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": null
   },
   {
    "source_name": "PIG-PIB – obszary zagrożone podtopieniami",
    "source_url": "https://cbdgmapa.pgi.gov.pl/arcgis/rest/services/hydrogeologia/podtopienia/MapServer",
    "licence": "PIG-PIB – dane publiczne, bezpłatne do ponownego wykorzystania z podaniem źródła",
    "retrieved_at": "2026-11-21T13:57:51.996065Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": null
   }
  ],
  "uncertainty": [
   "Brak strefy na mapach zagrożenia powodziowego nie wyklucza lokalnych podtopień (mapy obejmują tylko rzeki objęte MZP).",
   "Sieć rowów i cieków z BDOT10k (aktualność głównie 2012–2015) – rowy mogły zostać zasypane lub wykopane później; nazwy cieków nie są dostępne w tej usłudze.",
   "Dla otworów publiczna usługa podaje głębokość i typ, ale nie poziom wody ani wydajność – te dane są w kartach otworów CBDH (geoportal PIG-PIB)."
  ],
  "messages": [],
  "elapsed_ms": 752
 },
 "vegetation": {
  "key": "vegetation",
  "title": "Stan roślinności (satelita)",
  "status": "ok",
  "data": {
   "latest": {
    "date": "2024-06-23",
    "ndvi": 0.859,
    "ndmi": 0.475,
    "cloud_pct": 19.866242,
    "scene_id": "S2A_MSIL2A_20240623T100031_R122_T33UXT_20240623T160952"
   },
   "latest_age_days": 22,
   "series": [
    {
     "date": "2023-08-23",
     "ndvi": 0.27,
     "ndmi": null,
     "cloud_pct": 1.540579,
     "scene_id": "S2B_MSIL2A_20230823T095559_R122_T33UXT_20241019T191513"
    },
    {
     "date": "2023-09-07",
     "ndvi": 0.325,
     "ndmi": null,
     "cloud_pct": 0.004386,
     "scene_id": "S2A_MSIL2A_20230907T100031_R122_T33UXT_20230907T212618"
    },
    {
     "date": "2023-10-17",
     "ndvi": 0.258,
     "ndmi": null,
     "cloud_pct": 39.276874,
     "scene_id": "S2A_MSIL2A_20231017T100031_R122_T33UXT_20231017T165220"
    },
    {
     "date": "2024-04-09",
     "ndvi": 0.308,
     "ndmi": null,
     "cloud_pct": 32.652959,
     "scene_id": "S2B_MSIL2A_20240409T095549_R122_T33UXT_20240411T002033"
    },
    {
     "date": "2024-05-14",
     "ndvi": 0.276,
     "ndmi": null,
     "cloud_pct": 7.845422,
     "scene_id": "S2A_MSIL2A_20240514T100031_R122_T33UXT_20240514T141120"
    },
    {
     "date": "2024-06-23",
     "ndvi": 0.859,
     "ndmi": null,
     "cloud_pct": 19.866242,
     "scene_id": "S2A_MSIL2A_20240623T100031_R122_T33UXT_20240623T160952"
    }
   ],
   "baseline_same_doy": 0.754,
   "anomaly": 0.105,
   "in_growing_season": true
  },
  "provenance": [
   {
    "source_name": "Copernicus Sentinel-2 L2A (ESA) – Microsoft Planetary Computer (STAC + Data API)",
    "source_url": "https://planetarycomputer.microsoft.com/api/data/v1/item/statistics",
    "licence": "Copernicus Sentinel data 2024 (ESA) – bezpłatne, wymagane przypisanie; dane zmodyfikowane (NDVI/NDMI)",
    "retrieved_at": "2026-11-21T13:47:56.975645Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": "2024-06-23",
    "notes": "47 scen w serii (≤1/miesiąc IV–X); statystyki liczone dla granic działki"
   }
  ],
  "uncertainty": [
   "Najnowsze czyste zdjęcie ma 22 dni – stan roślin mógł się zmienić.",
   "NDVI (wskaźnik zieleni roślin, 0–1) i NDMI (wskaźnik wilgotności liści) to średnia z czystych pikseli całej działki (10 m) – las, droga albo kilka upraw na działce uśredniają wynik.",
   "Chmury i cienie maskujemy klasyfikacją SCL z ESA; pojedyncze zakłócenia mogą zostać."
  ],
  "messages": [],
  "elapsed_ms": 0
 },
 "land_cover": {
  "key": "land_cover",
  "title": "Użytkowanie terenu",
  "status": "partial",
  "data": {
   "classes": {
    "grunty orne": 99.4,
    "łąki i pastwiska (roślinność trawiasta)": 0.4,
    "las i zadrzewienia": 0.1,
    "zabudowa": 0.1
   },
   "agricultural_share_pct": 99.8,
   "source_used": "esa_worldcover_2021",
   "cropland_share_pct": 99.4,
   "bdot_classes": {}
  },
  "provenance": [
   {
    "source_name": "ESA WorldCover 10 m v200 (2021)",
    "source_url": "https://planetarycomputer.microsoft.com/api/data/v1/item/statistics",
    "licence": "CC BY 4.0 – © ESA WorldCover project 2021 / Copernicus Sentinel data (via Microsoft Planetary Computer)",
    "retrieved_at": "2026-11-21T13:49:44.198127Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "1426 pikseli 10 m w granicach działki"
   }
  ],
  "uncertainty": [
   "ESA WorldCover to mapa z 2021 r. (klasyfikacja satelitarna, dokładność ok. 75–80%) – obecne użytkowanie mogło się zmienić."
  ],
  "messages": [],
  "elapsed_ms": 0
 },
 "yields": {
  "key": "yields",
  "title": "Plony historyczne",
  "status": "ok",
  "data": {
   "official": [
    {
     "year": 2021,
     "crop": "pszenica",
     "yield_t_ha": 5.07,
     "level": "country",
     "unit_name": "Polska"
    },
    {
     "year": 2022,
     "crop": "pszenica",
     "yield_t_ha": 5.34,
     "level": "country",
     "unit_name": "Polska"
    },
    {
     "year": 2023,
     "crop": "pszenica",
     "yield_t_ha": 5.38,
     "level": "country",
     "unit_name": "Polska"
    },
    {
     "year": 2021,
     "crop": "pszenica",
     "yield_t_ha": 5.35,
     "level": "voivodeship",
     "unit_name": "Wielkopolskie"
    },
    {
     "year": 2022,
     "crop": "pszenica",
     "yield_t_ha": 5.53,
     "level": "voivodeship",
     "unit_name": "Wielkopolskie"
    },
    {
     "year": 2023,
     "crop": "pszenica",
     "yield_t_ha": 5.71,
     "level": "voivodeship",
     "unit_name": "Wielkopolskie"
    }
   ],
   "parcel_productivity_index": [
    {
     "year": 2021,
     "peak_ndvi": 0.825,
     "rel_index": 1.0
    },
    {
     "year": 2022,
     "peak_ndvi": 0.756,
     "rel_index": 0.92
    },
    {
     "year": 2023,
     "peak_ndvi": 0.87,
     "rel_index": 1.06
    },
    {
     "year": 2024,
     "peak_ndvi": 0.859,
     "rel_index": 1.04
    }
   ],
   "note": "Plony urzędowe GUS dotyczą całego województwa (i Polski), a nie Twojego pola – GUS nie publikuje plonów dla powiatów ani działek. Indeks z NDVI pokazuje, czy dany rok był na tej działce lepszy (>1) czy gorszy (<1) od typowego, ale nie przelicza się wprost na tony."
  },
  "provenance": [
   {
    "source_name": "GUS – Bank Danych Lokalnych (plony z 1 ha, ogółem)",
    "source_url": "https://bdl.stat.gov.pl/api/v1/data/by-variable/4332",
    "licence": "GUS – Bank Danych Lokalnych, otwarte dane (ponowne wykorzystanie z podaniem źródła)",
    "retrieved_at": "2026-11-21T13:51:47.869770Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "zmienna 4332: pszenica; dt/ha → t/ha"
   },
   {
    "source_name": "Indeks produktywności działki ze szczytowego NDVI (Sentinel-2)",
    "source_url": null,
    "licence": "obliczenia własne na danych Copernicus Sentinel",
    "retrieved_at": "2026-11-21T13:51:47.870134Z",
    "mode": "cached",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "szczytowe NDVI IV–IX danego roku / mediana z lat"
   }
  ],
  "uncertainty": [
   "Plony urzędowe GUS dotyczą całego województwa (i Polski), a nie Twojego pola – GUS nie publikuje plonów dla powiatów ani działek. Indeks z NDVI pokazuje, czy dany rok był na tej działce lepszy (>1) czy gorszy (<1) od typowego, ale nie przelicza się wprost na tony.",
   "Szczytowe NDVI zależy od uprawy w danym roku (płodozmian!) – porównuj lata z tą samą uprawą.",
   "Dane GUS za rok 2024 nie są jeszcze dostępne na dzień analizy."
  ],
  "messages": [],
  "elapsed_ms": 0
 },
 "protected_areas": {
  "key": "protected_areas",
  "title": "Obszary chronione",
  "status": "ok",
  "data": {
   "hits": [],
   "checked_layers": [
    "Natura 2000 – obszar ptasi (OSO)",
    "Natura 2000 – obszar siedliskowy (SOO)",
    "park narodowy",
    "rezerwat przyrody",
    "park krajobrazowy",
    "obszar chronionego krajobrazu",
    "zespół przyrodniczo-krajobrazowy",
    "użytek ekologiczny",
    "pomnik przyrody (powierzchniowy)",
    "obszar Ramsar (mokradła)"
   ],
   "nearby": []
  },
  "provenance": [
   {
    "source_name": "GDOŚ – Centralny Rejestr Form Ochrony Przyrody (WFS)",
    "source_url": "https://sdi.gdos.gov.pl/wfs",
    "licence": "Dane GDOŚ (Centralny Rejestr Form Ochrony Przyrody) – publiczne, bezpłatne, z podaniem źródła",
    "retrieved_at": "2026-11-21T13:57:52.589176Z",
    "mode": "live",
    "snapshot_date": null,
    "data_as_of": null,
    "notes": "10 warstw; przecięcie z geometrią działki"
   }
  ],
  "uncertainty": [
   "Granice form ochrony z rejestru GDOŚ; wiążące są akty prawne ustanawiające dany obszar.",
   "„W pobliżu” = w promieniu 1000 m od granic działki – może mieć znaczenie przy ocenie oddziaływania inwestycji (np. stawu, studni)."
  ],
  "messages": [],
  "elapsed_ms": 1345
 }
};

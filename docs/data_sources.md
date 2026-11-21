# Źródła danych – szczegóły techniczne (właściciel: zespół DATA)

Skrót i stan: AGENTS.md §4. Tutaj: dokładne warstwy, parametry zapytań, formaty odpowiedzi, limity, pułapki.
Każdy konektor dopisuje sekcję w formacie:

## <key> – <źródło>
- Endpoint / warstwy:
- Przykładowe zapytanie:
- Format odpowiedzi:
- Limity / czas odpowiedzi:
- Licencja:
- Pułapki:

## weather_history – Open-Meteo Archive → NASA POWER
- Open-Meteo: `https://archive-api.open-meteo.com/v1/archive?latitude&longitude&start_date&end_date&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration&timezone=Europe/Warsaw`
- NASA POWER: `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN&community=AG&longitude&latitude&start=YYYYMMDD&end=YYYYMMDD&format=JSON`
  (Rs w MJ/m²/d dla community=AG; fill_value -999; ET0 liczone FAO-56 PM w `science/et0.py`).
- Limity: Open-Meteo 429 przy wspólnym IP (21.11.2026); POWER ~1,5 s dla 10 lat.
- Licencje: Open-Meteo CC BY 4.0 (API darmowe niekomercyjnie); NASA POWER – domena publiczna.
- Pułapki: reanaliza, nie pomiar; POWER siatka ~50 km; opóźnienie ostatnich dni.

# Zatrzymaj wodę – asystent wodny dla działki rolnej

Prototyp na HackNation 2026 (zadanie KOWR „Zatrzymaj wodę, chroń plony”). Rolnik podaje numer działki ewidencyjnej
(albo klika mapę), datę i uprawę. Aplikacja zbiera na żywo publiczne dane o działce: meteo z 10 lat, suszę, glebę,
rzeźbę terenu, wody, satelitę, plony, okres wegetacji, wymagane pozwolenia i dofinansowania.

> **Dla agentów i deweloperów: zacznij od [AGENTS.md](AGENTS.md).**

## Szybki start
```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000   # API: http://127.0.0.1:8000/docs
cd frontend && npm install && npm run dev                                   # UI:  http://localhost:5173
```
Bez backendu: `cd frontend && VITE_USE_MOCKS=true npm run dev`. Testy: `make test`.

## Stan (F1 – dane)
Działają: lokalizacja działki (GUGiK ULDK), meteo z 10 lat (Open-Meteo, a przy limicie NASA POWER; ET0 FAO-56), prognoza,
lokalna baza wiedzy (prawo wodne, procedury, dofinansowania, prawo UE, uprawy). Pozostałe bloki są w budowie (AGENTS.md §4).

## Dokumentacja dla jury (pkt 4.2 zadania)
Sekcje do uzupełnienia przed zgłoszeniem: AGENTS.md §12.

---
Dane: GUGiK, IMGW-PIB, IUNG-PIB, Copernicus, NASA POWER, Open-Meteo (CC BY 4.0), Wody Polskie, PIG-PIB, GDOŚ, GUS, © OpenStreetMap.
Informacje prawne mają charakter orientacyjny.

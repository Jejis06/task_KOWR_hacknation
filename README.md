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

## Wdrożenie (Render, Docker)
Jeden kontener: FastAPI serwuje API (`/api/…`) i zbudowany frontend (`/`). Pliki: `Dockerfile`, `render.yaml`, `.github/workflows/keepalive.yml`.
1. Render → **New → Blueprint** → wskaż to (prywatne) repozytorium GitHub. Render zbuduje obraz z `Dockerfile` (plan `free`, region Frankfurt).
2. Po pierwszym wdrożeniu skopiuj adres usługi (np. `https://zatrzymaj-wode.onrender.com`).
3. GitHub → Settings → Secrets and variables → Actions → **Variables** → `RENDER_URL` = ten adres. Workflow „Keep alive” pinguje `/api/health` co 10 min, żeby darmowa usługa nie usypiała. Po hackathonie wyłącz go (zużywa minuty Actions w prywatnym repo).
4. Link do konkretnego raportu: `https://…/?dzialka=302504_5.0024.7&data=2026-07-15&uprawa=pszenica_ozima` (kilka działek: `dzialka=ID1+ID2`).

Lokalnie bez Dockera: `cd frontend && npm run build`, potem `cd backend && uv run uvicorn app.main:app --port 10000` – strona pod http://localhost:10000.

## Stan (F1 – dane)
Działają: lokalizacja działki (GUGiK ULDK), meteo z 10 lat (Open-Meteo, a przy limicie NASA POWER; ET0 FAO-56), prognoza,
lokalna baza wiedzy (prawo wodne, procedury, dofinansowania, prawo UE, uprawy). Pozostałe bloki są w budowie (AGENTS.md §4).

## Dokumentacja dla jury (pkt 4.2 zadania)
Sekcje do uzupełnienia przed zgłoszeniem: AGENTS.md §12.

---
Dane: GUGiK, IMGW-PIB, IUNG-PIB, Copernicus, NASA POWER, Open-Meteo (CC BY 4.0), Wody Polskie, PIG-PIB, GDOŚ, GUS, © OpenStreetMap.
Informacje prawne mają charakter orientacyjny.

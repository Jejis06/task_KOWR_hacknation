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

## Analiza AI i formalności (z projektu AgroLegal)

- **„Wytłumacz mi prosto”** nad raportem i czat **„Zapytaj o swoją działkę”** – OpenAI `gpt-5.4-mini` (`POST /api/llm/summary`,
  `POST /api/llm/chat`, kontrakt w `docs/llm_contract.md`). Klucz w `.env` jako `OPENAI_API_KEY` (wzór `.env.example`; na
  Renderze zmienna środowiskowa). **LLM wyjaśnia, nie decyduje**: ocena, formalności, opłaty i statusy naborów pochodzą z reguł;
  model dostaje fakty i przepisy jako ponumerowane źródła, linki i plakietki dobiera serwer (testy: `backend/tests/test_llm.py`).
  Bez klucza – teksty z szablonów.
- **Formalności przy każdym działaniu** (bez formalności / zgłoszenie / pozwolenie, opłata za rok analizy, urząd, czas) i sekcja
  **„Twój plan: co wolno i za ile”**; **dotacje ze statusem naboru**; **kalkulator oczka** (zagłębienie > 5000 m² → oczko 5000 m²
  na zgłoszenie); **wstępnie wypełnione zgłoszenie wodnoprawne** do druku: `/api/forms/zgloszenie?id=…&date=…`.
- Link prosto do widoku analityka: `?dzialka=…&data=…&uprawa=…&widok=dane`.
- **Wymagania obowiązkowe KOWR (pkt 3.3) działają bez LLM**: ocena, przyczyny, rekomendacje, nawadnianie, data, źródła,
  ograniczenia i brakujące dane liczy aplikacja z pobranych danych regułami. AI to wyłącznie dodatek nad raportem.
- **Widok rolnika**: wąska lewa kolumna (działka, mapa), szeroki środek. Na górze **„Podpowiedzi dla Twojego pola”** – 7 rozwijanych
  pytań (jak zatrzymać wodę, koszty, zysk, dotacje, formalności, co i kiedy; `POST /api/llm/faq`, odpowiedź liczona dopiero po
  rozwinięciu, zapas z reguł). Pod nimi raport jako rozwijane tematy (otwarty jeden naraz): woda → przyczyny → co zrobić →
  formalności i koszty → podlewanie → pogoda 16 dni → rośliny i kalendarz uprawy → ograniczenia i brakujące dane → źródła.
  Wydruk/PDF (przycisk lub Ctrl+P) rozwija wszystkie tematy. Szczegóły wszystkich bloków danych – zakładka „Wszystkie dane”.
- **WCAG 2.0, zasada 3 (zrozumiałość)**: `lang="pl"`, natywne rozwijane sekcje z nagłówkami (klawiatura, czytnik ekranu), spójne
  nazwy tych samych funkcji („Skąd to wiemy?”), błędy formularza powiązane z polem (`aria-invalid`, `role="alert"`) z podpowiedzią
  formatu, zmiana uprawy/daty nie uruchamia analizy sama, wyjaśnienia skrótów (NDVI, KBW…), prosty język, informacja o linkach
  otwieranych w nowej karcie.

## Stan (F1 – dane)
Działają: lokalizacja działki (GUGiK ULDK), meteo z 10 lat (Open-Meteo, a przy limicie NASA POWER; ET0 FAO-56), prognoza,
lokalna baza wiedzy (prawo wodne, procedury, dofinansowania, prawo UE, uprawy). Pozostałe bloki są w budowie (AGENTS.md §4).

## Dokumentacja dla jury (pkt 4.2 zadania)
Sekcje do uzupełnienia przed zgłoszeniem: AGENTS.md §12.

---
Dane: GUGiK, IMGW-PIB, IUNG-PIB, Copernicus, NASA POWER, Open-Meteo (CC BY 4.0), Wody Polskie, PIG-PIB, GDOŚ, GUS, © OpenStreetMap.
Informacje prawne mają charakter orientacyjny.

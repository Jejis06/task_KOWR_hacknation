# AgroLegal – Zachowaj kroplę dla siebie na dłużej

**Zespół:** Grimsby Brothers · **Zadanie:** KOWR „Zatrzymaj wodę, chroń plony”, HackNation 2026

**Działająca wersja:** http://51.12.82.24:3369
(przykładowy raport: http://51.12.82.24:3369/?dzialka=100209_2.0004.140&data=2025-07-15&uprawa=kukurydza_ziarno)

Rolnik wpisuje numer działki ewidencyjnej (albo adres, albo klika mapę), wybiera uprawę i datę. W ok. 10 sekund dostaje raport:
czy na działce brakuje wody i dlaczego, gdzie i jak ją zatrzymać, czy podlewać, czy na dane działanie potrzebne jest zgłoszenie
lub pozwolenie, ile to kosztuje i skąd wziąć dofinansowanie.

## Zespół i podział pracy

| Osoba | Zakres |
|---|---|
| **Ignacy Buczek** | backend: API (FastAPI), konektory danych (ULDK, pogoda, susza, gleba, teren, wody, satelita, pokrycie terenu, ochrona przyrody), analiza regułowa (ocena → przyczyny → rekomendacje → nawadnianie FAO-56), baza wiedzy (prawo wodne, opłaty, dotacje, uprawy), cache i obsługa limitów źródeł, testy, wdrożenie (Docker, serwer) |
| **Mateusz Portka** | frontend: interfejs rolnika i widok analityka (React), mapa z miejscami na wodę i zaznaczaniem działek, raport w rozwijanych tematach, wykresy, wydruk i PDF, dostępność (lupa, wysoki kontrast), asystent AI w interfejsie (podpowiedzi i czat); research: źródła danych, przepisy prawa wodnego, dotacje i literatura naukowa do bazy wiedzy |

Wspólnie: koncepcja rozwiązania, dobór źródeł danych, testy na działkach z całej Polski, dokumentacja.

## Opis rozwiązania

**Problem.** Dane o wodzie, glebie, suszy i terenie są publiczne, ale rozproszone po kilkunastu portalach i wymagają wiedzy z GIS,
hydrologii i prawa wodnego. Rolnik nie dostaje z nich prostej odpowiedzi „co mam zrobić na tej działce”. Do tego dochodzi pytanie,
którego zwykle nikt nie zadaje w narzędziach o suszy: czy mi wolno, w którym urzędzie i za ile.

**Główne funkcjonalności.**
- Wybór działki: numer (`TERYT.obręb.numer`), „obręb numer”, adres, kliknięcie mapy, obrys na mapie; do 25 działek naraz
  (sąsiednie działki liczone jako jedno pole).
- Raport w kolejności z zadania: ocena sytuacji wodnej → przyczyny → retencja → agrotechnika → nawadnianie.
- Mapa z miejscami na wodę: naturalne zagłębienia z modelu terenu, kierunki spływu, miejsca, gdzie woda ucieka z pola,
  proponowane działania (oczko, zastawka, pas zieleni, studnia).
- Formalności przy każdym działaniu: bez formalności / zgłoszenie / pozwolenie wodnoprawne, urząd, opłata za rok daty analizy,
  czas. Wstępnie wypełnione zgłoszenie wodnoprawne do druku.
- Koszty i dotacje ze statusem naboru (nie obiecujemy programów bez naboru).
- Data analizy z ostatnich 10 lat – analiza liczona „na tamten dzień”, bez danych z przyszłości.
- Zapis raportu do PDF i druk, pobranie danych (JSON), link do raportu (`?dzialka=…&data=…&uprawa=…`).
- Asystent AI (podpowiedzi nad raportem i czat o działce) – tylko tłumaczy raport, nie liczy oceny.
- Widok analityka „Wszystkie dane”: każdy blok danych z wartościami, wykresami, tabelą sezonów i źródłem.

**Sposób wykorzystania danych.** Dla wskazanej działki i daty aplikacja pobiera dane z 12 bloków (pogoda z 10 lat, prognoza, susza,
gleba, teren, wody, satelita, pokrycie terenu, ochrona przyrody, kalendarz uprawy, formalności, ocena) z publicznych źródeł
i liczy z nich wynik regułami opartymi na metodach naukowych (FAO-56, KBW i progi SMSR IUNG, NWRM). Przy każdej liczbie jest
źródło i data danych.

**Korzyści dla rolnika.** Jedno pole zamiast pięciu portali i trzech urzędów; konkretne działania dla tej działki z uzasadnieniem;
wiadomo od razu, co można zrobić bez urzędu, a co wymaga zgłoszenia; bez logowania, bez instalacji, działa na telefonie.

---

## 1. Instrukcja uruchomienia

**Najprościej:** otwórz http://51.12.82.24:3369 w przeglądarce (Chrome, Firefox, Edge, Safari, Opera; Windows, macOS, telefon).
Nic nie trzeba instalować ani zakładać konta. Uwaga: serwer działa po HTTP (bez certyfikatu), przeglądarka może pokazać „Niezabezpieczona”.

**Docker (jeden kontener: API + strona):**
```bash
docker build -t agrolegal .
docker run -p 10000:10000 -e OPENAI_API_KEY=… agrolegal     # klucz opcjonalny
```
Strona: http://localhost:10000. Bez klucza OpenAI wszystko działa, a podpowiedzi AI korzystają z szablonów.

**Lokalnie (deweloperski):** wymagane Python 3.12 z [uv](https://docs.astral.sh/uv/) i Node.js 22.
```bash
cd backend && uv sync && uv run uvicorn app.main:app --port 8000     # API i dokumentacja: http://127.0.0.1:8000/docs
cd frontend && npm install && npm run dev                            # strona: http://localhost:5173
```
Klucz AI (opcjonalnie): skopiuj `.env.example` do `.env` i wpisz `OPENAI_API_KEY`. Testy: `make test`.
Tryb bez internetu (tylko interfejs, dane przykładowe): `cd frontend && VITE_USE_MOCKS=true npm run dev`.

**Jak sprawdzić działkę:** wpisz numer działki, wybierz uprawę i datę, kliknij „Sprawdź działkę”. Link z parametrami od razu liczy
raport, np. `/?dzialka=302504_5.0024.7&data=2026-07-15&uprawa=pszenica_ozima` (kilka działek: `dzialka=ID1+ID2`,
widok analityka: `&widok=dane`). Działki testowe z 14 województw: [docs/test_parcels.md](docs/test_parcels.md).

## 2. Podstawowe funkcjonalności

Raport dla rolnika (zakładka „Raport”), w kolejności wymaganej przez KOWR:

1. **Jak jest z wodą?** – stan bieżący (bilans wodny z 60 dni względem normy z 10 lat, klasa suszy, anomalia zieloności i wilgotności
   liści z Sentinel-2) i podatność wieloletnia (w ilu z 10 sezonów była susza, kategoria gleby), poziom pewności oceny.
2. **Dlaczego brakuje wody?** – udziały przyczyn: deficyt opadów, niska retencja gleby, wrażliwość uprawy, odpływ powierzchniowy.
3. **Co zrobić, żeby zatrzymać wodę?** – działania retencyjne (zastawka na rowie, oczko w zagłębieniu poza strefą powodziową,
   pas zieleni tam, gdzie woda ucieka) i agrotechniczne (międzyplon z gatunkami i terminami siewu, mulcz, materia organiczna),
   ułożone od najważniejszego, z pinezkami na mapie.
4. **Czy to wymaga formalności i ile kosztuje?** – plan „co wolno i za ile”, urząd właściwy dla gminy, opłaty, dotacje ze statusem
   naboru, kalkulator oczka, gotowe zgłoszenie wodnoprawne.
5. **Czy podlewać?** – dobowy bilans wody w strefie korzeni (FAO-56) z prognozą: ile wody ubyło, za ile dni stres wodny, dawka.
   Nawadnianie zawsze na końcu, po retencji.

Dalej: prognoza pogody na 16 dni (dla dat bliskich dziś), kalendarz uprawy, **„Czego nie wiemy”** (ograniczenia i brakujące dane
wprost), **„Skąd są dane”** (metoda i źródła z datami). Przy każdej ocenie przycisk „Skąd to wiemy?” pokazuje liczby, blok danych,
datę i źródło.

Inne: mapa (zdjęcie lotnicze / mapa, granice działek, warstwy wody), zaznaczanie wielu działek, obrys, „Pokaż moją okolicę”,
wydruk/PDF (wszystkie tematy rozwinięte), pobranie danych, lupa 125%/150% i wysoki kontrast, czat o działce w obu widokach.

## 3. Architektura (skrót)

```
Przeglądarka (React 19 + Vite, Leaflet, Recharts)
   │  /api/parcel/resolve  → działka (ULDK GUGiK / eksport GeoParquet)
   │  /api/parcel/block/{key}?id=…&date=…&crop=…   × 12 bloków, równolegle
   │  /api/llm/{summary,faq,chat}   (opcjonalnie)
   ▼
FastAPI (Python 3.12) – jeden kontener Docker, serwuje też zbudowaną stronę
   ├─ konektory danych (backend/app/connectors): pogoda, susza, gleba, teren, wody, satelita, pokrycie, ochrona przyrody
   ├─ baza wiedzy (data/knowledge, YAML): prawo wodne, procedury i opłaty, dotacje, działania NWRM, 19 upraw (FAO-56)
   ├─ analiza regułowa (backend/app/knowledge/analysis.py): ocena → przyczyny → rekomendacje → nawadnianie
   ├─ LLM (backend/app/llm): tylko objaśnia gotowy raport, odpowiada z ponumerowanych źródeł
   └─ cache dyskowy (diskcache/SQLite): wyniki i kafelki mapy, przerwa po limicie źródła
```

Każdy blok ma ten sam kontrakt: `status` (ok / partial / no_data / error / not_applicable), dane, źródła z datą i licencją,
komunikaty. Blok, który się nie udał, nie zatrzymuje raportu – raport mówi, czego brakuje. Analiza (`analysis`) liczy się
z wyników pozostałych bloków dopiero po ich pobraniu, więc rekomendacje zawsze wynikają z oceny tej działki.

## 4. Źródła i zakresy danych

| Kategoria | Źródło | Zakres / rozdzielczość |
|---|---|---|
| Działka | GUGiK ULDK (`GetParcelByIdOrNr`, `GetParcelByXY`); eksport działek GeoParquet (opendata.geoportal.gov.pl) dla obrysu | granice ewidencyjne, cała Polska |
| Meteo – historia | Open-Meteo Archive (ERA5) → zapasowo NASA POWER; opad sprawdzany najbliższą stacją synoptyczną IMGW-PIB | dobowe: opad, temperatura, ET₀ (FAO-56 Penman–Monteith); 10 lat do daty analizy |
| Meteo – prognoza | Open-Meteo Forecast | 16 dni, gdy data analizy ≈ dziś |
| Susza | SMSR IUNG-PIB (tabele gmin, od 2020 r.); KBW działki wg progów SMSR; EDO Copernicus (CDI, SMA) | 10 lat, okresy raportowania SMSR |
| Gleba | IUNG-PIB kategorie podatności gleb na suszę (WMS); Mapa glebowo-rolnicza GUGiK; SoilGrids (ISRIC) zapasowo | kategoria gleby, retencja wody (TAW) |
| Teren | NMT GUGiK (usługa wysokości, siatka 8–20 m, działka + 300 m); zapasowo Copernicus DEM GLO-30 | spadek, zagłębienia (Priority-Flood), spływ D8, TWI, zlewnie |
| Wody | ISOK (mapy zagrożenia powodziowego), BDOT10k (cieki, rowy, zbiorniki do 1 km), PIG-PIB (otwory 3 km, GZWP, JCWPd, podtopienia) | otoczenie działki |
| Satelita | Sentinel-2 L2A przez Microsoft Planetary Computer (STAC + statystyki dla granic działki, maska chmur SCL) | NDVI i NDMI, ≤1 scena/miesiąc IV–X, 10 lat |
| Pokrycie terenu | ESA WorldCover 2021; BDOT10k | udział gruntów ornych, lasu, zabudowy w działce |
| Ochrona przyrody | GDOŚ (10 form: Natura 2000, parki narodowe, rezerwaty, parki krajobrazowe, OChK…) | działka i 1 km |
| Mapa (podkład) | Ortofotomapa i granice działek GUGiK (WMS), OpenStreetMap | kafelki przez nasz cache |
| Adresy | GUGiK UUG → zapasowo Nominatim (OSM) | wyszukiwanie adresu |
| Wiedza | 57 dokumentów: Prawo wodne (t.j. Dz.U. 2026 poz. 1335 i 1358), stawki opłat (M.P. 2025/717, 2026/430), ARiMR, Wody Polskie, CDR, IUNG, NWRM, POLSA | reguły formalności, opłat, dotacji, działań |

## 5. Dane pobierane na bieżąco i dane przygotowane wcześniej

**Na bieżąco, przy każdej analizie** (dla wskazanej działki i daty; wynik może trafić do cache, który tylko przyspiesza powtórkę):
działka (ULDK), pogoda historyczna i prognoza, susza (SMSR, EDO), gleba, model terenu, wody, sceny Sentinel-2, pokrycie terenu,
ochrona przyrody, adresy. Z tych danych aplikacja liczy ocenę, przyczyny, rekomendacje i nawadnianie – **nie wyświetlamy
wcześniej przygotowanych wyników.**

Cache (dysk serwera): dane historyczne 30 dni, dane bieżące kilka godzin, sceny satelitarne rok (obraz z przeszłości się nie zmienia),
działki 7 dni, kafelki mapy 30 dni.

**Przygotowane wcześniej (w repozytorium):**

| Co | Plik | Data pobrania / opracowania |
|---|---|---|
| Baza wiedzy: 57 dokumentów źródłowych (tekst) i reguły YAML (prawo wodne, procedury, opłaty 2026–2027, dotacje i nabory ARiMR 2026, działania NWRM, 19 upraw z fazami i Kc FAO-56) | `data/knowledge/` | dokumenty pobrane 21.11.2026 (`raw/manifest.json` z adresem, datą i sumą SHA-256); reguły opracowane 21–22.11.2026 |
| Lista stacji synoptycznych IMGW-PIB ze współrzędnymi | `data/imgw/synop_stations.json` | 21.11.2026 |

Baza wiedzy to przepisy i parametry (np. opłata za zgłoszenie, Kc pszenicy), a nie wyniki dla działek – ocenę i rekomendacje dla
konkretnej działki zawsze liczy aplikacja z danych pobranych w chwili analizy.

## 6. Biblioteki, komponenty, usługi zewnętrzne i AI

**Backend (Python):** FastAPI, Starlette, Pydantic, pydantic-settings, uvicorn, httpx, shapely, pyproj, numpy, scipy, rasterio (GDAL),
DuckDB (+ httpfs), diskcache, PyYAML. Skrypty: pypdf, python-docx.
**Frontend:** React, react-dom, Vite, TypeScript, Leaflet, Recharts, Radix UI (dialog, popover, slot), Tailwind CSS 4, tw-animate-css,
class-variance-authority, clsx, tailwind-merge, lucide-react. Narzędzia: ESLint, Vitest, Ruff, pytest.
**Usługi zewnętrzne:** wszystkie źródła z punktu 4 (bez kluczy, bezpłatne) oraz OpenAI API (opcjonalnie, płatne).

**Sztuczna inteligencja – w aplikacji:**
- Model: OpenAI `gpt-5.4-mini` (`backend/app/llm/`), używany w „Podpowiedziach dla Twojego pola” i czacie „Zapytaj o swoją działkę”.
- **AI nie liczy oceny, formalności, opłat ani kwot.** To robią reguły. Model dostaje gotowe fakty z raportu i fragmenty przepisów
  jako ponumerowane źródła i ma je przełożyć na prosty język; linki i plakietki statusu dobiera serwer, nie model. Gdy czegoś nie
  ma w danych, model ma to powiedzieć wprost. Pilnują tego testy `backend/tests/test_llm.py`.
- Bez klucza API wszystkie wymagane funkcje działają (podpowiedzi z szablonów).

**Sztuczna inteligencja – przy tworzeniu:** kod i dokumentację pisaliśmy z pomocą asystentów AI do programowania (m.in. Claude Code,
Anthropic). Każdą zmianę sprawdzaliśmy testami i ręcznie w aplikacji.

**Modele i metody analityczne (bez uczenia maszynowego):** FAO-56 (ET₀ Penman–Monteith, Kc, bilans wody w strefie korzeni),
klimatyczny bilans wodny i progi SMSR IUNG-PIB, Saxton–Rawls (retencja gleby z SoilGrids), Priority-Flood i D8 (zagłębienia i spływ),
TWI, katalog NWRM Komisji Europejskiej.

## 7. Licencje i warunki korzystania

**Kod i komponenty:** wyłącznie licencje otwarte pozwalające na dalsze wykorzystanie przez KOWR: MIT (FastAPI, Pydantic, pyproj,
DuckDB, PyYAML, React, Vite, Recharts, Radix, Tailwind, lucide), BSD (uvicorn, httpx, shapely, numpy, scipy, rasterio, Leaflet,
pypdf), Apache-2.0 (diskcache, TypeScript), ISC (lucide-react). Pełna tabela: [AGENTS.md §11](AGENTS.md).

**Dane:**

| Dane | Warunki |
|---|---|
| GUGiK (ULDK, NMT, ortofotomapa, granice działek, eksport działek, UUG, mapa glebowo-rolnicza) | bezpłatne, zasób PZGiK (art. 40a Prawa geodezyjnego i kartograficznego) |
| IMGW-PIB | dane publiczne, z podaniem źródła |
| IUNG-PIB (SMSR, kategorie gleb) | informacja publiczna, z podaniem źródła |
| Open-Meteo | CC BY 4.0; darmowe API do użytku niekomercyjnego (przy wdrożeniu komercyjnym – plan płatny lub własna instancja) |
| NASA POWER | domena publiczna |
| Copernicus (Sentinel-2, DEM GLO-30, EDO) | bezpłatne, z podaniem źródła |
| Microsoft Planetary Computer | bezpłatna usługa bez klucza; dane na licencjach źródłowych |
| ESA WorldCover, ISRIC SoilGrids | CC BY 4.0 |
| PIG-PIB, GDOŚ, PGW Wody Polskie (ISOK) | dane publiczne, z podaniem źródła |
| OpenStreetMap (podkład, Nominatim) | ODbL; ≤1 zapytanie/s do Nominatim, wyniki w cache |
| OpenAI API | regulamin OpenAI; płatne za użycie (opcjonalne) |

Informacje prawne w raporcie mają charakter orientacyjny i nie są poradą prawną – raport zawsze to zaznacza.

## 8. Znane ograniczenia

- **Pogoda z siatki, nie z pola:** ERA5 / ERA5-Land ma ok. 10–25 km, NASA POWER ok. 50 km. Opad sprawdzamy najbliższą stacją IMGW i pokazujemy różnicę.
- **Satelita:** chmury – bierzemy najnowszą czystą scenę przed datą analizy i podajemy jej wiek. Poza sezonem (XI–III) NDVI nie ma sensu,
  blok zwraca „nie dotyczy”. NDVI porównujemy z tą samą porą roku na tej działce w poprzednich latach; uprawa wpływa przez okres
  wegetacji z kalendarza uprawy, ale nie znamy upraw z poprzednich lat (płodozmian), więc norma jest mieszanką upraw.
- **Działka to nie zawsze pole:** w granicach może być las lub zabudowa – maskujemy to blokiem pokrycia terenu i mówimy o tym w raporcie.
- **Model terenu:** gdy NMT GUGiK nie odpowiada, bierzemy Copernicus DEM 30 m; na działkach poniżej 3 ha nie wyciągamy wtedy wniosków
  o zagłębieniach (za mała rozdzielczość).
- **SMSR IUNG** ma tabele gmin od 2020 r. – dla wcześniejszych lat suszę liczymy z bilansu wodnego działki.
- **Progi oceny i udziały przyczyn** to szacunek zespołu oparty na literaturze, nie oficjalna klasyfikacja. Pokazujemy to w raporcie.
- **Limity źródeł:** Open-Meteo i GUGiK potrafią ograniczać liczbę zapytań. Mamy źródła zapasowe, cache i przerwę po limicie, ale przy
  wyczerpanym limicie blok może mieć status „częściowe” albo „brak danych” – raport mówi to wprost.
- **Brak danych o plonach na poziomie działki** w źródłach publicznych.
- **Prawo i dotacje:** stan na listopad 2026 (Prawo wodne t.j. 2026, nabory ARiMR 2026). Ostateczną kwalifikację robi urząd.
- **Prototyp:** serwer bez HTTPS, jeden kontener, bez kolejki zadań.

## 9. Weryfikacja wyników i rekomendacji

- **Przejrzystość w raporcie:** przy każdej ocenie „Skąd to wiemy?” – liczby, blok danych, data i źródło z linkiem; sekcja „Jak powstała
  ocena” z metodą; sekcja „Czego nie wiemy” z brakującymi danymi i niepewnością; widok „Wszystkie dane” z surowymi wartościami
  i tabelą sezonów (opad, parowanie ET₀, bilans, najdłuższy okres bez deszczu dla każdego z 10 lat).
- **Testy automatyczne:** 174 testy backendu (pytest) i testy frontendu (Vitest): kontrakt bloków, reguły formalności i opłat,
  spójność bazy wiedzy (odwołania między plikami YAML), FAO-56, progi SMSR, zagłębienia i spływ, granice dat (bez danych z przyszłości),
  zachowanie przy limicie źródeł, ograniczenia AI. Uruchomienie: `make test`; testy na żywych źródłach: `make test-live`.
- **Sprawdzenie na działkach:** 17 działek rolnych z 14 województw ([docs/test_parcels.md](docs/test_parcels.md)), różne daty z 10 lat.
  Czas pełnej analizy bez cache: 8–12 s (cel KOWR: do 30 s).
- **Porównanie ze źródłami:** opad z siatki porównujemy ze stacją IMGW; klasę suszy z tabelami SMSR IUNG dla gminy; formalności
  i opłaty z tekstem ustawy i obwieszczeń (cytaty w bazie wiedzy).

## Skalowanie, koszty i bezpieczeństwo

**Limity źródeł.** Cache wyników na dysku (powtórka tej samej działki i daty – natychmiast), proxy kafelków mapy z cache,
źródła zapasowe (NASA POWER za Open-Meteo, Copernicus DEM za NMT, SoilGrids za mapę glebową, Nominatim za UUG), wykrywanie limitu
GUGiK i przerwa 90 s zamiast zasypywania serwera, ≤1 zapytanie/s do Nominatim, działki w obrysie czytane fragmentami z krajowego
GeoParquet (bez ULDK).

**Dla wielu rolników w całej Polsce:** pobrać hurtowo zbiory, które instytucje udostępniają w całości (eksport działek 4,6 GB,
Copernicus DEM dla Polski, BDOT10k, mapy ISOK, ERA5-Land z Copernicus CDS) i trzymać je lokalnie w GeoParquet/COG z indeksem
przestrzennym – aplikacja pyta najpierw lokalnie, a API tylko jako zapas. Odświeżanie: działki co tydzień, pogoda codziennie,
sceny satelitarne co 5 dni, przepisy przy zmianie. Przy większym ruchu: kilka instancji za load balancerem, wspólny cache (Redis),
kolejka zadań dla pierwszego liczenia działki; powtórne raporty z cache są natychmiastowe.

**Koszty.** Prototyp działa na jednej maszynie wirtualnej i zużywa ok. 200 MB RAM. Wersja z danymi trzymanymi lokalnie: maszyna
2–4 vCPU, 8 GB RAM i dysk ok. 1 TB w chmurze – rzędu 300–500 zł miesięcznie; dane publiczne bez opłat. OpenAI (opcjonalne): ułamek grosza za odpowiedź, wyniki w cache. Przy wdrożeniu komercyjnym:
płatny plan Open-Meteo lub własna instancja, ewentualnie własny model językowy.

**Bezpieczeństwo.** Bez logowania i bez danych osobowych (numer działki to dane publiczne z ewidencji). Zgłoszenie wodnoprawne
generujemy bez danych osobowych – rolnik wpisuje je ręcznie na wydruku. Klucz API tylko w zmiennej środowiskowej, poza repozytorium.
Walidacja wejścia (format numeru działki, zakres dat, maksymalny obrys 400 ha), limity czasu zapytań do źródeł, brak wykonywania
kodu z danych zewnętrznych.

---

Dokumentacja techniczna dla zespołu: [AGENTS.md](AGENTS.md) (bloki danych, kontrakt, zweryfikowane endpointy, dziennik prac).
Dane: GUGiK, IMGW-PIB, IUNG-PIB, Copernicus, NASA POWER, Open-Meteo (CC BY 4.0), Microsoft Planetary Computer, ESA, ISRIC,
PIG-PIB, GDOŚ, PGW Wody Polskie, © współtwórcy OpenStreetMap.

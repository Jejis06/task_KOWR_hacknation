# Zgłoszenie na platformę HackTribe – KOWR „Zatrzymaj wodę, chroń plony”

Teksty gotowe do wklejenia w pola formularza (pkt 4.1 zadania) i lista kontrolna.

## Pola formularza

**Nazwa zespołu:** Grimsby Brothers

**Tytuł rozwiązania:** AgroLegal – Zachowaj kroplę dla siebie na dłużej

**Problem:**
Dane o wodzie, glebie, suszy i terenie są publiczne, ale rozproszone po kilkunastu portalach i wymagają wiedzy z GIS, hydrologii
i prawa wodnego. Rolnik nie dostaje z nich odpowiedzi, co zrobić z wodą na swojej działce, czy na to działanie potrzebne jest
zgłoszenie albo pozwolenie, w którym urzędzie i ile to kosztuje.

**Główne funkcjonalności:**
Rolnik wpisuje numer działki (albo adres, albo klika mapę), wybiera uprawę i dowolną datę z ostatnich 10 lat. W ok. 10 sekund
dostaje raport w kolejności KOWR: ocena sytuacji wodnej (teraz i w 10 latach) → przyczyny niedoboru → działania retencyjne z
miejscami na mapie (zagłębienie na oczko, zastawka na rowie, pas zieleni) → agrotechnika (międzyplon z terminem siewu, mulcz,
materia organiczna) → czy podlewać (bilans wody w strefie korzeni FAO-56 z prognozą). Przy każdym działaniu: czy wymaga
zgłoszenia lub pozwolenia, urząd, opłata, dotacje ze statusem naboru i wstępnie wypełnione zgłoszenie wodnoprawne. Raport do
PDF i druku, „Czego nie wiemy” z ograniczeniami, asystent AI, który tylko objaśnia raport.

**Sposób wykorzystania danych:**
Dla działki i daty aplikacja pobiera na żywo 12 bloków danych z publicznych źródeł: GUGiK (ULDK, NMT, ortofotomapa), IMGW-PIB,
Open-Meteo/ERA5 i NASA POWER (10 lat pogody), IUNG-PIB (SMSR, kategorie gleb), Sentinel-2 (NDVI, NDMI, 10 lat), ISOK, BDOT10k,
PIG-PIB, GDOŚ, ESA WorldCover, SoilGrids. Wynik liczą reguły oparte na FAO-56, klimatycznym bilansie wodnym i progach SMSR IUNG
oraz katalogu NWRM. Przy każdej liczbie jest źródło i data danych. AI nie liczy oceny ani kwot.

**Najważniejsze korzyści dla użytkownika:**
Jedno pole zamiast pięciu portali i trzech urzędów. Konkretne działania dla tej działki z uzasadnieniem danymi. Od razu wiadomo,
co można zrobić bez urzędu, a co wymaga zgłoszenia i za ile. Bez logowania, bez instalacji, działa na telefonie, duży tekst
i wysoki kontrast.

**Link do repozytorium (prywatne):** https://github.com/Jejis06/task_KOWR_hacknation

**Link do działającej wersji:** http://51.12.82.24:3369

**Przykładowy raport na żywo:** http://51.12.82.24:3369/?dzialka=100209_2.0004.140&data=2025-07-15&uprawa=kukurydza_ziarno

## Pliki do załączenia

| Element (pkt 4.1) | Plik / stan |
|---|---|
| Prezentacja PDF (do 10 slajdów) | `Każda kropla ma adres.pdf` – 10 slajdów (uwagi poniżej) |
| Dokumentacja README | `README.md` w repozytorium (9 punktów z pkt 4.2 + skalowanie, koszty, bezpieczeństwo, AI) |
| Wygenerowane raporty | `docs/zgloszenie/raport_100209_2.0004.140_2025-07-15_kukurydza.pdf`, `docs/zgloszenie/raport_302504_5.0024.7_2026-11-22_pszenica_ozima.pdf` |
| Film do 3 minut | **do nagrania** |
| Działający prototyp | http://51.12.82.24:3369 + instrukcja uruchomienia w README |

## Lista kontrolna przed wysłaniem

- [ ] Repozytorium pozostaje **prywatne**; dodać konta jury zgodnie z instrukcją na platformie (GitHub → Settings → Collaborators).
- [ ] Film do 3 minut: numer działki → raport → mapa z miejscami na wodę → formalności i zgłoszenie → PDF.
- [ ] Prezentacja: poprawki z sekcji niżej, eksport do PDF.
- [ ] Serwer 51.12.82.24:3369 działa w czasie oceny (jury sprawdza działki z całej Polski i daty z 10 lat).
- [ ] Po wydarzeniu: zmienić hasło do serwera, wyłączyć workflow „Keep alive”.

## Uwagi do prezentacji

Zgodna z wymaganiami (PDF, 10 slajdów). Liczby ze slajdów 1, 5 i 6 sprawdzone na produkcji dla działki 100209_2.0004.140
(15.07.2025, kukurydza) – zgadzają się. Kody QR prowadzą do działającego raportu. Do poprawy:

1. Brak nazwy zespołu „Grimsby Brothers” na slajdach – dodać na slajdzie 1 i 10.
2. Slajdy 1 i 6: etykiety pinezek na mapie nachodzą na siebie („Zbiornik” zasłonięty przez „Pas zieleni”).
3. Slajd 4: „Dane pobierane na żywo – nic przygotowanego wcześniej” jest za mocne – baza przepisów i opłat jest przygotowana
   wcześniej (z datą pobrania). Lepiej: „dane o działce pobierane na żywo; przepisy i opłaty z datą pobrania”.
4. Slajd 9: „tekst do 125%” – aplikacja ma też 150%.

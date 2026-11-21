# Zadanie KOWR – streszczenie dla agentów

Oryginały: `docs/zadanie/01_tresc_zadania.pdf`, `02_regulamin.pdf`, `03_podstawy_naukowe.pdf`.

## Co budujemy
Prototyp aplikacji webowej dla rolnika bez wiedzy GIS. Rolnik podaje działkę ewidencyjną (numer albo mapa), uprawę i datę.
Aplikacja pobiera dane (meteo, satelitarne, glebowe, hydrologiczne, przestrzenne; bieżące i z 10 lat), liczy wynik i zwraca raport:
1. **Ocena stanu wilgotności**: wskaźniki satelitarne + gleba + meteo, 10 lat; interpretacja satelity zależna od uprawy.
2. **Rekomendacje retencyjne i agrotechniczne**: rzeźba terenu, cieki i zbiorniki, uprawa → gdzie i jak zatrzymać wodę, zabiegi zwiększające retencję glebową.
3. **(Opcjonalnie) nawadnianie**: zasadność, termin, zakres.

Kolejność ma znaczenie: **ocena → przyczyny → retencja → agrotechnika → nawadnianie**. Bez rozpoznania działki nie ma rekomendacji.
„Wyświetlenie wcześniej przygotowanych rekomendacji nie spełnia wymagań.”

## Raport musi zawierać
Stan niedoboru i przyczyny; rekomendacje uzasadnione danymi; datę i źródła danych; ograniczenia (aktualność, dokładność, niepewność, czynniki pominięte).
Brak danych komunikujemy wprost, bez pozornej precyzji. Raport można zapisać w systemie, jako PDF albo wydrukować.

## Testowanie przez jury
- **Etap 1:** jury uruchamia prototyp dla **tych samych działek z całej Polski** (numer działki) i **dat (dziś albo historyczne z 10 lat)**.
  Wyniki porównuje z **danymi referencyjnymi** jury (hipoteza: SMSR IUNG-PIB / EDO).
- **Finał (3–5 zespołów):** pitch 2–3 min + do 2 min pytań, demo na żywo dla 1–3 działek i dat wskazanych przez jury.

## Kryteria
| Kryterium | Waga |
|---|---|
| Wartość praktyczna (konkretne decyzje, lokalne warunki) | 25% |
| Dane i wiarygodność (łączenie źródeł, zgodność z nauką, niepewność) | 25% |
| Innowacyjność i potencjał (integracja, skalowanie) | 20% |
| Prostota obsługi | 15% |
| Działający prototyp (stabilność, kod, bezpieczeństwo, dokumentacja, licencje, **≤30 s**) | 15% |

## Wymagania formalne (zgłoszenie)
Nazwa zespołu i tytuł; opis (problem, funkcje, użycie danych, korzyści); link do **prywatnego** repo; README (9 punktów – AGENTS.md §12);
prezentacja PDF do 10 slajdów; film do 3 min; wygenerowane raporty; działający link albo instrukcja uruchomienia.
Skalowalność opisana w README: limity źródeł i cache, aktualizacja danych, czas odpowiedzi, koszty infrastruktury.
Zwycięzca nieodpłatnie przenosi autorskie prawa majątkowe na KOWR, więc licencje komponentów muszą na to pozwalać.

## Podstawy naukowe (KOWR)
Bilans wodny (nie tylko opad), integracja danych (FAO-56, SMSR IUNG). Rozróżniać suszę bieżącą od podatności wieloletniej.
Przyczyny: deficyt opadów + temperatura; niska retencja gleby (mało materii organicznej, gleby lekkie); odpływ powierzchniowy (stoki, brak mokradeł i zadrzewień); wymagania uprawy.
Zasada „retain water where it falls”: retencja krajobrazowa (zbiorniki, oczka, mokradła, strefy buforowe, zadrzewienia) i glebowa (międzyplony, resztki, ograniczenie uprawy, materia organiczna) **przed** nawadnianiem.
Rozwiązanie ma wskazywać niepewność i uzasadniać rekomendacje danymi.
Bibliografia: FAO-56; Doroszewski i in. 2012 (SMSR); KE NWRM 2014/2015; FAO 2019; Minasny i in. 2017 (4 per mille); Żyłowska & Kozyra 2025.
Polecane przez ekspertów: PAK „Dane satelitarne dla administracji” (rozdz. 6.3.3–6.3.4); CDR e-poradnik „Melioracje, retencja i gospodarka wodna” 2025.

## Mentorzy
dr inż. T. Bolewski (susza, bilans wodny) · B. Czerniejewski (UX, potrzeby użytkownika) · dr hab. D. Gozdowski (agrotechnika, dane satelitarne) · T. Rychlicki (GIS, dane publiczne, API).

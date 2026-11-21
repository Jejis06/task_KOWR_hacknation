# Decyzje UX (właściciel: zespół PRODUCT)

Użytkownik: rolnik bez wiedzy GIS, często na telefonie w polu. Kryteria KOWR: prostota obsługi 15%, wartość praktyczna 25%.

## Przepływ

1. **Wejście:** numer działki (pełny identyfikator `302504_5.0024.7` albo „obręb numer”, np. `Słupia Wielka 7`) **albo** kliknięcie pola na mapie.
   Data analizy (dziś albo ostatnie 10 lat) i uprawa (opcjonalnie) są w jednym formularzu; kliknięcie mapy używa daty i uprawy z formularza.
2. **Walidacja na miejscu:** komunikat przy polu („Identyfikator wygląda na niepełny. Wzór: …”), bez wysyłania żądania.
   Błędy serwera tłumaczone na prosty polski (404 → „Nie znaleziono działki… sprawdź numer albo kliknij mapę”).
3. **Wynik progresywny:** każdy blok pobierany osobno i równolegle, karta pokazuje szkielet ładowania, pasek postępu „Pobieram dane: 7 z 12”.
   Jeden wolny lub zepsuty blok nie blokuje pozostałych (granica błędów per karta).
4. **Raport:** przycisk „Drukuj / zapisz PDF” (aktywny po pobraniu wszystkich bloków). Widok `@media print`: nagłówek z działką,
   datą analizy, uprawą i czasem wygenerowania; wszystkie bloki; procedury rozwinięte; panel „Skąd te dane” od nowej strony; bez formularza i JSON.

## Zasady prezentacji

- **Żadna liczba bez jednostki, źródła i daty.** `num()`/`signed()` zawsze dodają jednostkę; brak wartości = „brak danych” (nigdy samo „–”).
  Stopka każdej karty: źródło (link), tryb (na żywo / pamięć podręczna / kopia lokalna z datą), „dane do …” albo „pobrano …”, licencja.
- **Brak danych wprost:** statusy `no_data` / `not_applicable` / `error` / `not_implemented` mają własne zdania po polsku; niepewność w żółtej
  ramce „Ograniczenia i niepewność” w każdej karcie i zbiorczo w panelu „Skąd te dane”.
- **Bez żargonu:** skróty (KBW, NDVI, ET₀, Kc, TUZ, SMSR, NMT, TWI, GZWP, ISOK, RDOŚ…) jako `<Term>` – dymek po najechaniu, fokusie lub dotknięciu.
  Kategorie SMSR gleby opisane słowami („kat. I – gleby bardzo lekkie: bardzo podatne na suszę”), położenie terenu ikoną i zdaniem.
- **Plony:** zawsze z dopiskiem „średnie plony GUS – powiat, nie Twoje pole”.
- **Prawo:** karty pogrupowane „bez formalności / wymaga zgłoszenia / wymaga pozwolenia / zależy od sytuacji”; przy każdej: status wiedzy
  (potwierdzone / do weryfikacji / szacunek), fakty o działce (📍), czego nie sprawdzono, opłata na rok daty analizy, procedura krok po kroku,
  oficjalny wzór wniosku (gov.pl) i źródła. Zawsze disclaimer; nigdy „na pewno nie potrzebujesz zgody”.
- **Mapa:** podkład OSM albo ortofotomapa GUGiK, granice działek KIEG od zoomu 15; warstwy z bloków: zagłębienia (niebieskie), linie spływu
  (przerywane), wody z odległością w dymku.

## Dostępność i urządzenia

- Mobile-first: 1 kolumna < 960 px, sticky formularz + mapa po lewej na desktopie, 2 kolumny kart od 1250 px. Przy 375 px brak poziomego
  przewijania (tabele przewijają się w swoich ramkach).
- Pola i przyciski ≥ 48 px wysokości, czcionka 16 px+, widoczny fokus (`:focus-visible`), link „Przejdź do treści”, `aria-busy` na kartach,
  `aria-live` na pasku postępu, `role="img"` + opis dla wykresów i paska sezonu, `prefers-reduced-motion`.
- Kolory tekstu dobrane pod WCAG AA (≥ 4,5:1): `--muted #4f5b52`, `--warn #8a4b00`, `--err #a4211a`, `--green #0a6b2c`.
- Bez zewnętrznych fontów, analityki, cookies i logowania.

## Tryb mock

`VITE_USE_MOCKS=true` (albo konfiguracja `frontend-mock` w `.claude/launch.json`, port 5174): wszystkie bloki z syntetycznych danych
oznaczonych „MOCK” (baner na górze strony). Kształt danych 1:1 z kontraktem – gdy blok Agenta A przejdzie na ✅, podmienia on mock prawdziwą próbką.

## Znane braki

- Brak testów w Safari/Edge/Opera i Firefoksie z poziomu agenta (testowano Chromium: 375 px i desktop).
- Wydruk mapy zależy od przeglądarki (kafelki mogą się nie zdążyć załadować).
- Raport F3 (ocena, przyczyny, rekomendacje) jeszcze nie istnieje – widok druku to zalążek z danymi.

# BAZA WIEDZY: woda w gospodarstwie rolnym w Polsce
### Analiza gruntu, źródła wody, retencja, melioracje, prawo wodne, procedury, dofinansowania

Stan wiedzy: 20.11.2026.

**Oznaczenia:**
- **[OK]**: potwierdzone w źródle (linki w sekcji 14).
- **[DO WERYFIKACJI]**: niepewne albo wymaga potwierdzenia.
- **[SZACUNEK]**: wartość orientacyjna.

---

## 1. Kontekst: HackNation 2026, zadanie KOWR

**Oficjalny opis z listy zadań (dosłownie, stan 16.11.2026):**
> **Inicjator projektu:** KRAJOWY OŚRODEK WSPARCIA ROLNICTWA
> **Kampania:** ZATRZYMAJ WODĘ, CHROŃ PLONY
> „Zmiany klimatu stawiają przed polskim rolnictwem coraz większe wyzwania. Podejmij wyzwanie i zaprojektuj rozwiązanie, które pomoże rolnikom podejmować trafniejsze decyzje, chronić plony i budować bardziej odporne na zmiany klimatu gospodarstwa.”

KOWR realizuje projekt **S2MUR** (System Satelitarnego Monitorowania Upraw Rolnych), zamawiany przez MRiRW, z IUNG-PIB jako wykonawcą (sekcja 9) [OK].

---

## 2. Dane publiczne o gruncie, wodzie i klimacie

| Warstwa | Źródło | Dostęp | Ograniczenia |
|---|---|---|---|
| Działka ewidencyjna (geometria, TERYT, gmina, obręb, numer) | GUGiK **ULDK** | `https://uldk.gugik.gov.pl/?request=GetParcelByXY&xy=lon,lat,4326&result=geom_wkb,teryt,voivodeship,county,commune,region,parcel&srid=4326`; linia 1 odpowiedzi = status („0” = OK), linia 2 = pola rozdzielone „\|”, geometria w WKB hex; także GetParcelById [OK] | działka ≠ pole uprawne |
| Numeryczny model terenu 1 m i 5 m, chmury punktów LiDAR | GUGiK | bezpłatny, dowolne użycie [OK]; moduł „Pobierz dane” na geoportal.gov.pl, skorowidze, usługi WCS/WFS, eksport GeoTIFF, formaty ASC / ARC GRID; WMS/WMTS do podglądu | 1 km² przy siatce 1 m = 1 mln punktów; cała Polska ok. 313 mld punktów [OK] |
| Mapa glebowo-rolnicza (kompleksy przydatności rolniczej, typy gleb, uziarnienie) | GUGiK, opracowanie IUNG | WMS `https://mapy.geoportal.gov.pl/wss/service/pub/guest/MapaGlebowoRolnicza/MapServer/WMSServer` (WMTS analogicznie); GML w PZGiK dla części województw (na wniosek); materiały IUNG: `https://opendata.geoportal.gov.pl/Mapy/mapa_glebowo-rolnicza.zip` | dane z lat 60–80; dla większości woj. podkarpackiego brak kompleksów przydatności [OK]; pełny nowy GML m.in. dla małopolskiego [OK] |
| Klasy bonitacyjne (klasoużytki) | ewidencja gruntów i budynków (EGiB), powiatowe usługi WMS | atrybut „KLASOUZYTKI_EGIB” w warstwie działek | jakość i dostępność zależą od powiatu |
| Podatność gleb na suszę | IUNG + GUGiK | WMS „Podatność gleb na susze” na geoportalu, moduł „Rolnictwo” [OK]; w S2MUR raster 10 m | — |
| Susza rolnicza | **SMSR IUNG-PIB** | `susza.iung.pulawy.pl`: klimatyczny bilans wodny i zagrożenie suszą dla wszystkich 2477 gmin, per gatunek uprawy i kategoria gleby [OK] | poziom gminy |
| Pogoda (temperatura, wilgotność, opad) | **IMGW** | `https://danepubliczne.imgw.pl/api/data/synop` (bez klucza, aktualizacja co godzinę), dane archiwalne dobowe | sieć stacji rzadka; API nie podaje współrzędnych stacji |
| Klimat w siatce, ewapotranspiracja ET₀ | ERA5-Land (np. przez Open-Meteo) | API | reanaliza, niska rozdzielczość |
| Przepływy rzek (SNQ, SSQ) | archiwum IMGW (hydro) | dane historyczne | tylko posterunki wodowskazowe |
| Strefy zagrożenia powodziowego | **ISOK / Hydroportal** (Wody Polskie) | mapy zagrożenia i ryzyka powodziowego: scenariusze 0,2%, 1%, 10%, z głębokościami; WMS; wtyczka QGIS „Wody Polskie – Baza WMS” (32 usługi) [OK] | tylko wybrane rzeki; wyniki modeli dla scenariuszy statystycznych, a nie bieżąca sytuacja; nie obejmują zalań od opadów |
| Zlewnie, cieki, jednolite części wód (JCWP) | **MPHP 1:10 000** (Wody Polskie) | WMS/WFS, wtyczka QGIS | — |
| Hydrogeologia | **PIG-PIB**: Centralny Bank Danych Hydrogeologicznych (CBDH, ok. 130 tys. obiektów), Mapa Hydrogeologiczna Polski 1:50 000 (m.in. głębokość do pierwszego poziomu wodonośnego, litologia), Główne Zbiorniki Wód Podziemnych (GZWP), zasoby dyspozycyjne | WFS otworów: `https://cbdgmapa.pgi.gov.pl/arcgis/services/hydrogeologia/cbdh_otwory/MapServer/WFSServer`; raporty xlsx/csv na wniosek [OK] | skala 1:50 000 zgrubna; zasoby dyspozycyjne w skali regionu |
| Obiekty topograficzne (rowy, cieki, drogi, budynki, lasy) | BDOT10k | pobieranie z geoportalu, wtyczka QGIS GUGiK | — |
| Uzbrojenie terenu | KIUT | WMS | — |
| Plany miejscowe | KIMP | WMS | — |
| Natura 2000, rezerwaty, parki narodowe | GDOŚ, geoserwis | WMS/WFS | — |
| Ortofotomapa | GUGiK | WMS `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution` (warstwa „Raster”) | — |
| Kataster wodny, SIGW | Wody Polskie | kataster: wgląd nieodpłatny [OK]; dane z SIGW na wniosek | brak otwartego API |
| Ewidencja urządzeń melioracji wodnych i gruntów zmeliorowanych | Wody Polskie | aktualizacja inwentaryzacji finansowana z KPO (umowy 12.2024) [OK] | [DO WERYFIKACJI] zakres i termin udostępnienia; w Polsce brak otwartej mapy drenaży |

---

## 3. Analiza terenu i wody: metody

- **Hydrologia z NMT:** wypełnianie zagłębień (algorytm Priority-Flood), kierunki spływu D8 lub D-inf, akumulacja spływu, wyznaczanie zlewni i cieków, zagłębienia jako naturalne miejsca gromadzenia wody, indeks wilgotności TWI, scenariusz „deszcz X mm → gdzie stanie woda”. Narzędzia: WhiteboxTools, GRASS (r.watershed), SAGA, pysheds, richdem, rasterio, geopandas. Implementacja w czystym numpy/scipy liczy 1 km² w siatce 1 m w ok. 5 s; dla większych obszarów stosuje się resampling do 2–5 m.
- **Woda nie zna granic działek:** analiza spływu wymaga obszaru zlewni lub co najmniej bufora (rzędu 200–500 m) wokół działki.
- **Bilans napełnienia zbiornika:** V_roczna ≈ powierzchnia zlewni × opad × współczynnik odpływu − ET₀ × powierzchnia lustra wody. Współczynnik odpływu dla pól to kilka–kilkanaście % [SZACUNEK], więc wynik podaje się jako widełki.
- **Szczelność dna:** gliny i iły zatrzymują wodę; piaski wymagają uszczelnienia, co podnosi koszt.
- **Zapotrzebowanie na wodę do nawadniania:** ET₀ × współczynnik uprawy − opad, przeliczone na średnią roczną m³/dobę (istotne dla progu 5 m³/dobę, sekcja 5).
- **Susza:** bilans opad − parowanie + retencja gleby; odniesienie: SMSR, S2MUR.
- **Powodzie rzeczne:** mapy ISOK są wynikiem modeli hydraulicznych dla scenariuszy; zalań od opadów nawalnych poza rzekami nie obejmują.

---

## 4. Kryteria lokalizacji zbiornika retencyjnego (wiedza dziedzinowa)

**Wykluczenia lub poważne ograniczenia:**
- strefa szczególnego zagrożenia powodzią (odrębna procedura, ryzyko zniszczenia);
- kolizja z budynkami, drogami, sieciami (BDOT10k, EGiB, KIUT);
- lasy i użytki ekologiczne (inne przepisy);
- cudzy grunt: bez tytułu prawnego nie ma zgłoszenia ani dotacji ARiMR;
- strefy ochronne ujęć wody (zakaz robót ziemnych);
- rezerwaty i parki narodowe.

Natura 2000 i obszar chronionego krajobrazu nie wykluczają, ale komplikują procedurę (możliwe uzgodnienia z RDOŚ).

**Czynniki korzystne:**
- naturalne zagłębienie terenu (mniej kopania = taniej);
- odpowiednio duża zlewnia zasilająca w stosunku do objętości;
- grunt szczelny (gliny, iły);
- płytka woda gruntowa (staw zasilany wodą gruntową mieści się w wariancie „na zgłoszenie”);
- bliskość pól z deficytem wody;
- lokalizacja na gruncie słabszym (nieużytek, wymok), a nie na klasach I–IIIa;
- położenie przy rowie (zbiornik + zastawka mogą działać jako magazyn dla systemu melioracji).

**Uwagi prawne:**
- zbiornik ≤5000 m² i ≤3 m głębokości, zasilany tylko opadami, roztopami lub wodą gruntową, z oddziaływaniem w granicach własnego gruntu, wymaga jedynie zgłoszenia (sekcja 5);
- kilka stawów na jednym gruncie się sumuje.

---

## 5. Prawo wodne i budowlane [OK, chyba że oznaczono inaczej]

### 5.1. Pobór wody
- **Zwykłe korzystanie z wód** (bez zgód): przysługuje właścicielowi gruntu, na potrzeby własne i gospodarstwa domowego lub rolnego, przy poborze średniorocznie ≤5 m³/dobę. To średnia roczna, więc w sezonie wegetacyjnym pobór może być większy.
- **Nawadnianie upraw:** pobór wód to usługa wodna, a nawadnianie gruntów lub upraw to szczególne korzystanie z wód → **pozwolenie wodnoprawne**. Nawadnianie wodą podziemną za pomocą deszczowni zawsze wykracza poza zwykłe korzystanie.
- **Pobór z cieku publicznego** pompą do nawadniania wymaga pozwolenia wodnoprawnego. [DO WERYFIKACJI: granice „powszechnego korzystania z wód”, które dotyczy korzystania bez specjalnych urządzeń technicznych.]
- **Studnia do 30 m** na potrzeby zwykłego korzystania: bez pozwolenia i bez zgłoszenia. **Studnia głębsza niż 30 m** albo pobór w ramach usług wodnych (>5 m³/dobę lub działalność gospodarcza): pozwolenie wodnoprawne, plus wymagania Prawa geologicznego i górniczego (zatwierdzenie projektu robót geologicznych, dokumentacja hydrogeologiczna, jeśli wymagana).
- **Abolicja dla studni:** nowelizacja Prawa wodnego (ustawa z 19.06.2026) weszła w życie 18.08.2026 (część źródeł podaje 17.08). Złożenie kompletnego wniosku o legalizację do **31.12.2027** pozwala uniknąć opłaty legalizacyjnej (ok. 6,6 tys. zł) i kar administracyjnych (od 5 tys. do 1 mln zł). Dotyczy ujęć wymagających zgody. Szacunkowo może skorzystać ok. 40 tys. gospodarstw.
- **Opłaty za usługi wodne:** pobór wód podziemnych 0,068 zł/m³ (rozporządzenie RM z 26.10.2023). Pobór do nawadniania w rolnictwie i leśnictwie jest zwolniony z opłaty stałej. Opłatę ustala zarząd zlewni; kwoty do 20 zł nie podlegają uiszczeniu.

### 5.2. Stawy i zbiorniki
- **Staw ≤5000 m² i ≤3 m głębokości**, napełniany wyłącznie wodami opadowymi, roztopowymi lub gruntowymi (nie w ramach usług wodnych), o zasięgu oddziaływania w granicach własnego gruntu: **zgłoszenie wodnoprawne**. Na gruntach rolnych taki staw nie wymaga pozwolenia na budowę.
- Staw większy albo zasilany z cieku: pozwolenie wodnoprawne.
- W starszych publikacjach podawane są nieaktualne progi (500 m² i 2 m, albo 1000 m²).
- Zbiornik bez szczelnej izolacji, zasilany wodami gruntowymi lub opadowymi albo połączony z ciekiem, jest w świetle Prawa wodnego urządzeniem wodnym niezależnie od wielkości.
- Małe szczelne oczko do 50 m², niewpływające na stosunki wodne: bez formalności budowlanych. Niewielki staw ziemny bez materiałów budowlanych zwykle nie wymaga zgłoszenia budowlanego; grobla, mnich czy przepust wymagają sprawdzenia w starostwie.
- Kilka stawów na jednym gruncie się sumuje; nadzór wodny może nakazać pozwolenie.

### 5.3. Rowy i melioracje
- **Zatrzymywanie wody w istniejącym rowie:** bez zgłoszenia i pozwolenia. **Przebudowa rowu** w celu odprowadzania wody wymaga pozwolenia. Przy rowie przebiegającym przez kilka działek potrzebna jest zgoda właścicieli sąsiednich gruntów (w praktyce porozumienie albo spółka wodna).
- Wykonanie urządzeń melioracyjnych wymaga pozwolenia albo zgłoszenia wodnoprawnego.
- **Utrzymanie urządzeń melioracji wodnych** należy do zainteresowanych właścicieli gruntów, a jeśli urządzenia są objęte działalnością spółki wodnej lub związku spółek wodnych, to do nich. Art. 205: w kosztach utrzymania uczestniczy ten, kto odnosi korzyść.
- Spółka wodna to dobrowolne zrzeszenie (min. 3 osoby). Nie jest właścicielem rowów, tylko administratorem, i nie może egzekwować obowiązków od osób spoza spółki.
- Ewidencję urządzeń melioracji wodnych prowadzą Wody Polskie.

### 5.4. Organy i procedury
- **Struktura Wód Polskich:** Krajowy Zarząd Gospodarki Wodnej (KZGW) → regionalne zarządy gospodarki wodnej (RZGW) → zarządy zlewni (ZZ) → nadzory wodne (NW).
- **Zgłoszenie wodnoprawne** przyjmuje **kierownik nadzoru wodnego** właściwego dla miejsca inwestycji. Składa się je **przed rozpoczęciem robót**, osobiście lub listownie (karta usługi gov.pl nie przewiduje drogi elektronicznej). Zgłoszenie jest publikowane w BIP Wód Polskich w ciągu 7 dni. Organ ma **30 dni** na sprzeciw w drodze decyzji; przy brakach termin biegnie od kompletnego zgłoszenia. Zgłoszenie wygasa po 3 latach od zgłoszonego terminu rozpoczęcia.
- **Pozwolenie wodnoprawne** wydaje dyrektor **zarządu zlewni** albo **RZGW**, zależnie od rodzaju przedsięwzięcia. Załączniki:
  - operat wodnoprawny z datą wykonania;
  - opis działalności bez specjalistycznych określeń;
  - decyzja o środowiskowych uwarunkowaniach (jeśli wymagana);
  - wypis i wyrys z planu miejscowego (jeśli dotyczy);
  - dokumentacja hydrogeologiczna (jeśli wymagana);
  - dowód opłaty, a przy pełnomocniku także pełnomocnictwo z opłatą skarbową.
  - Jeden wniosek może obejmować kilka pozwoleń, wtedy opłata się mnoży.
- **Kolejność zgód:** decyzja środowiskowa (jeśli wymagana) zawsze pierwsza → pozwolenie lub zgłoszenie wodnoprawne → pozwolenie lub zgłoszenie budowlane.
- **Ocena wodnoprawna:** dla przedsięwzięć mogących wpłynąć na osiągnięcie celów środowiskowych JCWP; wniosek do zarządu zlewni lub RZGW. Jeśli wymagana jest decyzja środowiskowa, ocena wodnoprawna odbywa się w jej ramach.
- **Legalizacja urządzenia wodnego** wykonanego bez zgody: wniosek do Wód Polskich, z mapą sytuacyjno-wysokościową i szkicami urządzenia.
- **Po wykonaniu urządzenia:** zgłoszenie do Systemu Informacyjnego Gospodarowania Wodami (SIGW); zmiany danych w ciągu 30 dni.
- **Opłaty administracyjne** [OK]: od 1.01.2026 (M.P. 2025 poz. 717) zgłoszenie 132,33 zł, pozwolenie 330,07 zł (kilka różnych pozwoleń w jednej decyzji: maks. 6601,67 zł), ocena wodnoprawna 1320,35 zł. Od 1.01.2027 (M.P. 2026 poz. 430): 137,09 / 341,95 / 1367,88 zł. Stawki bazowe z art. 398 (87 / 217 / 868 zł) są co roku waloryzowane. Strona „Katalog opłat” Wód Polskich podaje tylko rachunki.
- **Czas:** zgłoszenie zwykle 1–2 miesiące; pozwolenie od kilku miesięcy do ponad roku [SZACUNEK; oficjalnych średnich brak].
- **Wzory i poradniki:** karty usług gov.pl (pozwolenie, zgłoszenie), wzór wniosku o pozwolenie (także na biznes.gov.pl), FAQ Wód Polskich, poradniki „Pobór wód na potrzeby działalności rolniczej” i „Melioracje wodne w ustawie Prawo wodne”, Q&A „Zgoda wodnoprawna krok po kroku” (12.2024).
- **Rejestry:** kataster wodny gromadzi m.in. dane o pozwoleniach wodnoprawnych dotyczących poboru wody i odprowadzania ścieków; wgląd jest nieodpłatny. SIGW to system wewnętrzny Wód Polskich. Odrębnego publicznego rejestru pozwoleń nie ma; resort odrzucił petycję o jego utworzenie, wskazując SIGW.

---

## 6. Problemy rolników z formalnościami wodnymi

1. **Nieświadomość obowiązków:** według wiceminister rolnictwa wielu rolników nie wie, że od lat korzysta z urządzeń bez wymaganego pozwolenia.
2. **Limit 5 m³/dobę i kary:** w czasie suszy Wody Polskie prowadzą kontrole; kary w głośnych sprawach rolniczych sięgały 60–100 tys. zł i obejmowały kilka lat wstecz.
3. **Czas i złożoność procedury:** operat, czasem decyzja środowiskowa, wypisy z planów, składanie osobiście lub listownie; pozwolenie trzeba mieć przed sezonem, a nie w trakcie suszy.
4. **Melioracje i rozmyta odpowiedzialność:** rowy to obiekty liniowe, więc zaniedbanie jednego właściciela psuje cały system; spółki wodne są dobrowolne i nie mogą egzekwować obowiązków; rolnicy skarżą się, że płacą składki, a rowy pozostają zarośnięte; w kontroli NIK jedna ze spółek miała środki na ok. 10% potrzebnych prac konserwacyjnych.
5. **Ograniczony wpływ rolników i gmin:** interpelacja poselska wskazuje, że procesy przeniesiono do „formuły pozwoleniowej, trudnej i czasochłonnej”; ministerstwo analizuje „problemy prawne blokujące rozwój spółek wodnych i odbudowę melioracji”.
6. **Zmienność przepisów:** nowe progi dla stawów, czasowa abolicja dla studni.

---

## 7. Finansowanie inwestycji wodnych (stan 11.2026)

**Mechanizm ARiMR / PS WPR:** większość dotacji inwestycyjnych to refundacja. Kolejne kroki:
1. nabór z regulaminem;
2. wniosek online (punkty, ranking);
3. umowa;
4. realizacja z własnych środków;
5. wniosek o płatność;
6. zwrot części kosztów;
7. okres związania celem.

Inwestycje trwale związane z nieruchomością są wspierane tylko na gruntach będących własnością wnioskodawcy (lub w użytkowaniu wieczystym).

**Brak dedykowanego programu:** dla pojedynczego rolnika nie ma obecnie programu dedykowanego budowie zbiorników retencyjnych.

| Program | Kto składa | Na co / ile | Status |
|---|---|---|---|
| Kredyt z gwarancją FGR Plus (I.10.1.2, BGK) | rolnik, przez bank | gwarancja do 80% kredytu; dopłata 60% raty odsetkowej do 24 mies.; oprocentowanie ≤6% | nabór ciągły |
| ARiMR I.10.1.1 (inwestycje zwiększające konkurencyjność) | rolnik | 65% kosztów kwalifikowanych dla rolników ≤40 lat lub gospodarstw ekologicznych, 45% dla pozostałych | nabory okresowe; [DO WERYFIKACJI] czy zbiornik jest kosztem kwalifikowanym |
| I.10.4 Inwestycje przyczyniające się do ochrony środowiska i klimatu | rolnik lub grupa rolników (min. 3) | m.in. systemy retencji wody (np. zbiorniki na wodę opadową); rolnik do 65%, grupa do 80% | [DO WERYFIKACJI] terminy naborów |
| Ekoschemat „Retencjonowanie wody na trwałych użytkach zielonych” | rolnik, we wniosku obszarowym | roczna płatność ok. 260,69 zł/ha [SZACUNEK]; warunek: zalanie lub podtopienie TUZ (≥80% wysycenia profilu glebowego) między 1 maja a 30 września | co roku |
| Interwencja rolno-środowiskowo-klimatyczna 8 (ochrona torfowisk i obszarów podmokłych) | rolnik | wariant 8.1 TUZ: 581 zł/ha/rok | co roku |
| Grupy Operacyjne EPI (I.13.5) | konsorcjum: min. 1 rolnik + min. 1 inny partner | etap 1: wsparcie przygotowawcze do 50 000 zł; etap 2: realizacja operacji (pilotaż); punkty za liczbę rolników | w obecnej WPR nabory się kończą (przygotowawcze 15.01–16.02.2026; realizacja: jeden nabór w 2026); najpewniej wróci w nowej WPR od 2028 |
| NFOŚiGW „Adaptacja do zmian klimatu” | [DO WERYFIKACJI, prawdopodobnie samorządy i instytucje] | ok. 900 mln zł dotacji i pożyczek na odporność na susze i powodzie | nabór 1.10.2026 – 30.09.2034 |
| FEnIKS / FEPW: mała i średnia retencja (NFOŚiGW) | samorządy, instytucje | ok. 8 mld zł łącznie | rolnik pośrednio, przez projekt gminy |
| LIFE (Komisja Europejska) + współfinansowanie NFOŚiGW | gminy, NGO, konsorcja | duże projekty środowiskowo-klimatyczne | współfinansowanie: nabór 12.05.2026 – 30.12.2027 |
| „Mikroretencja” (WFOŚiGW) | osoby fizyczne z domem jednorodzinnym | do 90%, max 8 tys. zł | nie dla działalności rolniczej |
| KPO B3.3.1, obszar B | gminy (projekty dla mieszkańców wsi) | zbiorniki retencyjne, urządzenia melioracyjne | **usunięte z KPO**; projekty miały się zakończyć do 12.12.2025 |

Uwaga: w mediach krążyła informacja o „206 mln euro z KPO na wodę w gospodarstwach” (Super Biznes). Wobec usunięcia B3.3.1 jest to informacja niewiarygodna.

---

## 8. Stan infrastruktury melioracyjnej i retencja

**Polska:**
- Użytki rolne ok. 18,9 mln ha (2010); zmeliorowano ok. 6,4–6,7 mln ha (ok. 70% potrzeb), głównie urządzeniami **odwadniającymi** (drenowanie, rowy).
- Tylko ok. 0,45–0,5 mln ha ma urządzenia nawadniające.
- Odwodniono ok. 2 mln ha siedlisk hydrogenicznych (doliny, obniżenia), z czego tylko ok. 0,5 mln ha wyposażono w urządzenia umożliwiające nawadnianie.
- Brak kontroli odpływu wynika ze złego stanu zastawek, braku konserwacji i problemów organizacyjnych.
- **Wody Polskie** 2020–2023: 338 działań, remont 1030 urządzeń wodnych → dodatkowe 9 mln m³ retencji na obszarze ok. 45 tys. ha gruntów rolnych. Ogółem ok. 1200 zmodernizowanych urządzeń, ok. 45 tys. ha nawodnionych gruntów. Przykład: zlewnia Stobrawy (remont zastawek z samorządem, spółkami wodnymi i rolnikami).
- **Jak działają piętrzenia i zastawki:** woda nie spływa szybko, zostaje dłużej w okolicy i stopniowo zasila wody gruntowe. Efekt jest niemal natychmiastowy.
- Inwentaryzacja urządzeń melioracji: Wody Polskie zakończyły ją w 15 zarządach zlewni; aktualizacja w kolejnych 6 zarządach (ponad 20 mln zł z KPO, umowy 12.2024).

**Dania:**
- Drenaż od lat 50. XIX w.; do 1907 r. objął 26% użytków rolnych (w latach 1871–1881 zdrenowano 300 tys. ha). Dziś ok. 60% kraju to rolnictwo, z czego ok. połowa jest sztucznie odwadniana.
- **Skjern Å:** największa rzeka Danii pod względem przepływu, wyprostowana i obwałowana w latach 60. (ostatnia duża melioracja w Danii). W latach 2001–2002 dolny odcinek 19 km zamieniono w 26 km rzeki meandrującej (obszar ok. 2200 ha). Ocena po 10 latach: rzeka odzyskała połączenie z doliną, ale naturalne siedliska i procesy wracają bardzo powoli.
- **Porozumienie „Zielone trójporozumienie” (2024):** ponad 30 mld DKK na ponowne nawodnienie 140 tys. ha gruntów rolnych bogatych w węgiel (gleby organiczne) i posadzenie 250 tys. ha lasów; łącznie ok. 43 mld DKK na przekształcenie użytkowania ziemi; pierwszy na świecie podatek od emisji z hodowli.
- **Rozwiązania na wylotach drenów:** sztuczne mokradła i bioreaktory ze zrębkami. Mokradło 0,2–0,3 ha oczyszcza wodę drenarską z ok. 100 ha. SEGES wykonał analizę GIS obszarów odpowiednich pod sztuczne mokradła (zlewnia Odense: ok. 23 tys. ha).
- Planowanie w zlewniach „ID15” (każda ok. 1500 ha gruntów ornych, ok. 3000 w kraju).
- Uniwersytet w Aarhus opracował krajową mapę obszarów zdrenowanych (z prawdopodobieństwem drenażu) i mapę odpływu drenarskiego (dane z 53 stacji).
- **SCALGO Live:** duńska platforma z krajową mapą zalań od nawalnych deszczy (z infiltracją i odprowadzaniem do kanalizacji); ma też korekty hydrologiczne i pokrycie terenu dla Polski.

---

## 9. Instytucje i systemy

- **IUNG-PIB Puławy** (Instytut Uprawy Nawożenia i Gleboznawstwa – Państwowy Instytut Badawczy):
  - ponad 160 lat tradycji, sieć 77 stacji meteorologicznych;
  - prowadzi SMSR (od 2007; komunikaty są podstawą potwierdzenia zagrożenia suszą w gminie i pomocy suszowej);
  - autor kompleksów przydatności rolniczej i współtwórca WMS „Podatność gleb na susze”;
  - nowe mapy glebowe z uczeniem maszynowym (gęstość objętościowa, frakcja ilasta; ponad 16 tys. punktów);
  - wykonawca S2MUR;
  - publikacja „Gospodarka wodna w rolnictwie jako element adaptacji do zmian klimatu” (Studia i Raporty IUNG-PIB 71(25), 2023);
  - kontakt: iung@iung.pulawy.pl, tel. 81 4786 700; mapy: mapy@iung.pulawy.pl.
- **S2MUR:**
  - projekt MRiRW realizowany przez KOWR, wykonawca IUNG-PIB, okres 12.2020–12.2026, wdrożenie 10.2026, koszt ok. 38,7 mln zł brutto;
  - cele: dokładniejsze szacowanie strat suszowych na poziomie działek, monitoring rozszerzony z 14 do 25 pozycji (w tym łąki i pastwiska);
  - funkcje: nieodpłatny geoserwis suszowy, mapa podatności gleb na suszę (raster 10 m), informacje agrometeorologiczne, API dla ARiMR (straty dla działek) i dla Portalu Rolnika;
  - nie zawiera rekomendacji dotyczących działań ani doboru roślin.
- **Wody Polskie (PGW):** zgody wodnoprawne, opłaty za usługi wodne, utrzymanie wód, kataster wodny, SIGW, Hydroportal, programy remontu urządzeń wodnych.
- **Aplikacja suszowa MRiRW** (`aplikacje.gov.pl/app/susza`): wnioski o oszacowanie szkód suszowych, powiązane z wynikami SMSR.
- **eDWIN:** cyfrowa platforma doradcza ośrodków doradztwa rolniczego (głównie ochrona roślin).
- **OnGeo:** komercyjne raporty o działkach (m.in. dane z mapy glebowej, informacje planistyczne).

---

## 10. Rolnictwo w Polsce: dane ogólne

- Ok. 1,3 mln gospodarstw rolnych; średnia powierzchnia ok. 12,4 ha (wzrost z 11,3 ha w 2010); w latach 2010–2020 najszybciej rosła liczba gospodarstw powyżej 50 ha.
- Inwestycje w nawadnianie w gospodarstwie mogą obejmować zarówno studnię, jak i system ciśnieniowy; każda inwestycja wymaga innych dokumentów, zależnie od wielkości i rodzaju.

---

## 11. Luki w dostępnych danych i informacjach

- Brak otwartej, ogólnopolskiej mapy drenaży i urządzeń melioracyjnych (ewidencja Wód Polskich w aktualizacji).
- Brak publicznego rejestru pozwoleń wodnoprawnych i brak API do składania zgłoszeń i wniosków.
- Dane glebowe historyczne (lata 60–80), część obszarów bez kompleksów.
- Hydrogeologia w skali 1:50 000; wydajność i jakość wody lokalnie tylko z pobliskich otworów.
- Mapy powodziowe bez zalań od opadów nawalnych.
- SMSR na poziomie gminy; dostępność publiczna S2MUR [DO WERYFIKACJI].
- Brak oficjalnych danych o średnim czasie wydawania pozwoleń.
- Koszty orientacyjne (studnia głębinowa za metr, staw za m³, zastawka, uszczelnienie) [DO WERYFIKACJI].

---

## 12. Punkty do weryfikacji
1. ~~Opłaty za zgłoszenie, pozwolenie i ocenę wodnoprawną~~ – zweryfikowane 21.11.2026 (M.P. 2025 poz. 717, M.P. 2026 poz. 430).
2. Uprawnieni wnioskodawcy w NFOŚiGW „Adaptacja do zmian klimatu”.
3. Kwalifikowalność zbiornika w ARiMR I.10.1.1 i I.10.4; terminy naborów. **Częściowo rozstrzygnięte 21.11.2026:** I.10.4 – zbiorniki na wodę opadową kwalifikowane (PODR, ulotka 12.2025: „Systemy retencji wody – np. zbiorniki wodne do magazynowania wody opadowej”; warunki: do 300 ha, min. 6 pkt); w harmonogramie ARiMR 2026 (stan po 22.06.2026) brak naborów I.10.1.1 i I.10.4; FGR Plus (I.10.1.2) – nabór ciągły; EPI realizacja operacji 1.10–2.11.2026. Nadal otwarte: zbiornik w I.10.1.1.
8. **Rozstrzygnięte 21.11.2026:** próg stawu na zgłoszenie = 5000 m² i 3 m (art. 394 ust. 1 pkt 9 Prawa wodnego, t.j. Dz.U. 2026 poz. 1335); broszura gov.pl „Inwestycje w nawadnianie” podaje nieaktualne 1000 m². Decyzja środowiskowa (wójt/burmistrz) m.in. dla stawów ≥3 m głębokości, studni ≥100 m, poboru ≥10 m³/h, melioracji ≥5 ha.
4. Granice powszechnego korzystania z wód przy poborze z cieku.
5. Publiczny dostęp do S2MUR (geoserwis, API).
6. Zakres i termin udostępnienia ewidencji melioracji Wód Polskich.
7. Nazwy warstw w usługach WMS/WFS (mapa glebowa, ISOK, GDOŚ, CBDH, MHP).

---

## 13. Materiały wideo
- NMT z geoportalu w QGIS i Blenderze (PL): https://www.youtube.com/watch?v=NFi-t8LbzPc
- Pobieranie danych GUGiK w QGIS: https://www.youtube.com/watch?v=vIBIivqp2GY
- Zlewnie i cieki z NMT (r.watershed): https://www.youtube.com/watch?v=Ud_9ZAPVlsg
- Whitebox w QGIS: ścieżki spływu i zagłębienia terenu (Whanganui): https://www.youtube.com/watch?v=Rhye-_IPwNs
- WhiteboxTools Python API: https://www.youtube.com/watch?v=1pUDBuwp1QY
- Whitebox Workflows, zlewnia w Pythonie: https://www.youtube.com/watch?v=lG0mdnCW8mk
- Mała retencja, rolnicze studium przypadku (z problemami prawnymi): https://www.youtube.com/watch?v=qIfVv97XTMQ

---

## 14. Źródła

**Geodane**
- NMT: https://www.geoportal.gov.pl/dane/numeryczny-model-terenu ; https://geoportal.gov.pl/en/data/digital-elevation-model-dem
- ULDK i EGiB: https://uldk.gugik.gov.pl/?lang=en ; https://www.geoportal.gov.pl/pl/dane/ewidencja-gruntow-i-budynkow-egib/
- Mapa glebowa WMS: https://www.geoportal.gov.pl/aktualnosci/usluga-wms-prezentujaca-mape-glebowo-rolnicza-dostepna-w-serwisie-www-geoportal-gov-pl/
- Mapa glebowa, Podkarpacie: https://www.geoportal.gov.pl/aktualnosci/mapa-glebowo-rolnicza-w-nowym-schemacie-aplikacyjnym-gml-dla-calosci-wojewodztwa-podkarpackiego-dostepna-w-pzgik/
- Mapa glebowa, Małopolska: https://www.geoportal.gov.pl/aktualnosci/mapa-glebowo-rolnicza-w-nowym-schemacie-aplikacyjnym-gml-dla-wojewodztwa-malopolskiegodostepna-w-pzgik-oraz-nowa-usluga-wmts-prezentujaca-mape-glebowo-rolnicza-dostepnaw-serwisie-www-geoportal-gov-pl/
- Podatność gleb na susze: https://www.geoportal.gov.pl/aktualnosci/nowa-usluga-wms-podatnosc-gleb-na-susze-dostepna-w-serwisie-www-geoportal-gov-pl-w-module-rolnictwo/
- Hydroportal: https://www.gov.pl/web/wody-polskie/isok--narzedzie-do-zarzadzania-ryzykiem-powodziowym
- Wtyczka QGIS Wody Polskie: https://plugins.qgis.org/plugins/wody_polskie_wms/
- CBDH: https://inspire-geoportal.ec.europa.eu/srv/api/records/094bffd6-0c5b-4efe-8a3d-6226bc0d03c8
- PIG-PIB, dane hydrogeologiczne: https://www.pgi.gov.pl/dokumenty-pig-pib-all/forum-panstwowej-sluzby-geologicznej/11-forum-psg/11660-p05-dane-hydrogeologiczne-kartograficzne-i-obiektowe-jozef-mikolajkow.html

**Prawo wodne i procedury**
- Zgłoszenie wodnoprawne: https://www.gov.pl/wody-polskie/zgloszenie-wodnoprawne
- Pozwolenie wodnoprawne: https://www.gov.pl/wody-polskie/pozwolenie-wodnoprawne
- FAQ Wód Polskich: https://www.gov.pl/web/wody-polskie/faq
- Zwykłe korzystanie, studnia 30 m: https://www.gov.pl/web/wody-polskie-szczecin/pobor-wod-w-ramach-zwyklego-korzystania-a-wymog-posiadania-pozwolenia-wodnoprawnego
- Limit 5 m³ jako średnia roczna: https://www.gov.pl/attachment/50a3e196-dc1f-4469-81c3-f5545a462606
- Poradnik „Pobór wód na potrzeby działalności rolniczej”: https://www.gov.pl/attachment/3135adea-c2ea-4ed0-81b7-86fcfee30c49
- Poradnik „Melioracje wodne w ustawie Prawo wodne”: https://www.gov.pl/attachment/4d6ba9e8-a3c1-4cb6-86c5-1f51179f8ac5 ; https://wody.gov.pl/images/Melioracje/melioracje_wodne-A5-4_kwietnia_2022.pdf
- Q&A „Zgoda wodnoprawna krok po kroku”: https://www.gov.pl/attachment/e303ca62-4871-4948-9c9a-b47606e01f41
- Struktura organów, zgody: https://www.gov.pl/attachment/4634b669-058c-4026-bc9f-b2e9c5435d71
- Inwestycje w nawadnianie, kolejność zgód: https://www.gov.pl/attachment/a9a2b555-9c77-4bc1-992b-487ef6614b4d
- Ocena wodnoprawna: https://www.gov.pl/web/wody-polskie-wroclaw/zalatw-sprawe
- Legalizacja urządzenia wodnego: https://www.gov.pl/web/wody-polskie/legalizacja-urzadzenia-wodnego
- Zatrzymywanie wody w rowach: https://wodnesprawy.pl/wp-content/uploads/2024/11/wodne-sprawy-kompendium_21_202448.pdf
- 30 dni / 3 lata (art. 423): https://arslege.pl/prawo-wodne/k1639/a106915/ ; https://lexlege.pl/tt/art-423/
- Staw bez pozwolenia na budowę: https://blog.ongeo.pl/staw-lub-zbiornik-wodny-bez-pozwolenia-na-budowe
- Oczko a urządzenie wodne: https://muratordom.pl/prawo/porady-prawne/niby-oba-to-woda-a-jednak-sa-inne-oczko-wodne-czy-staw-czym-roznia-sie-wedlug-przepisow-aa-b1Je-Nah1-wmMq.html
- Opłaty za wodę: https://api.sejm.gov.pl/sejm/term10/interpellations/attachment/ATTDRKK7Z/i14782-o1.pdf ; https://www.gov.pl/web/wody-polskie-warszawa/ozuw ; https://www.prawo.pl/samorzad/zwolenienie-od-oplaty-stalej-za-pobor-wody-efekt-uboczny-nie,440601.html
- Abolicja: https://www.blog.ongeo.pl/abolicja-nielegalna-studnia-legalizacja-prawo-wodne-2026 ; https://samorzad.gov.pl/web/gmina-mucharz/darmowa-legalizacja-studni-glebinowych--sprawdz-jak-z-niej-skorzystac ; https://www.infor.pl/tematy/studnia/ ; https://forsal.pl/gospodarka/aktualnosci/artykuly/10599260,mozesz-pozegnac-sie-ze-swoja-woda-ze-studni-jesli-nie-dopelnisz-tej-formalnosci-rzad-zapowiada-kontrole-a-kary-sa-wysokie-nowe-przepisy-2026.html
- Kataster wodny: https://lexlege.pl/prawo-wodne/art-155/ ; https://www.prawo.pl/samorzad/kataster-wodny-zawiera-dane-dot-pozwolen-wodnoprawnych-oraz-pozwolen-zintegrowanych,101988.html
- Petycja o rejestr pozwoleń: https://www.gov.pl/attachment/85eb2734-2d76-44a0-bae2-e5c55dc77e24
- Opłata za pozwolenie (Forsal): https://forsal.pl/kraj/aktualnosci/artykuly/11247513,zakaz-korzystania-ze-studni-nie-uzyjesz-jej-do-podlania-trawy-ani-w-gospodarstwie-domowym.html

**Melioracje i retencja**
- Utrzymanie melioracji: https://www.gov.pl/web/wody-polskie/utrzymanie-urzadzen-melioracji-wodnych
- Spółki wodne: https://www.prawo.pl/biznes/spolki-wodne-i-melioracja-sporo-problemow-do-rozwiazania,1537037.html ; https://www.prawo.pl/samorzad/kto-odpowiada-za-utrzymanie-rowow-meliracyjnych-i-przydroznych,510408.html
- NIK, spółka wodna: https://bip.nik.gov.pl/kontrole/wyniki-kontroli-nik/pobierz,lop~k_13_007_201309121409181378987758~id3~01,typ,kj.pdf
- Retencja dla rolnictwa: https://www.gov.pl/web/wody-polskie/retencja-dla-rolnictwa
- Działania Wód Polskich 2020–2023: https://www.gov.pl/web/wody-polskie/susza-retencja-dzialania-wod-polskich-dla-zwiekszania-zasobow-wodnych
- Retencja w Bydgoszczy, Stobrawa: https://www.gov.pl/web/wody-polskie-bydgoszcz/retencja-wody---klucz-do-przetrwania-rolnictwa-w-czasach-klimatycznych-ekstremow
- Ewidencja melioracji (KPO): https://www.gov.pl/web/wody-polskie/ponad-20-mln-zl-na-aktualizacje-ewidencji-urzadzen-melioracji-wodnych-oraz-gruntow-zmeliorowanych-na-terenie-szesciu-zarzadow-zlewni
- Statystyki melioracji: https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-article-BAR8-0013-0008/c/httpwww_pimr_poznan_plbiul20113bpr.pdf ; https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-article-BATC-0011-0001/c/Nyc_Pokladek.pdf ; https://agro.icm.edu.pl/agro/element/bwmeta1.element.agro-article-1a0690df-6e9c-4bef-b425-817dc5058526/c/147-151.pdf
- Interpelacja o spółkach wodnych: https://api.sejm.gov.pl/sejm/term10/interpellations/13346/body
- Kontrole i kary (Bezprawnik): https://bezprawnik.pl/limit-poboru-wody-ze-studni/

**IUNG, S2MUR, Dania**
- IUNG oferta: https://www.gov.pl/attachment/ff15f079-bab8-4a90-8c4a-266d69e567ab
- S2MUR: https://www.iung.pl/wp-content/uploads/2026/08/1.-Opis-zalozen-projektu-informatycznego-S2MUR.pdf
- SMSR: https://wiescirolnicze.pl/susza-rolnicza-w-polsce-dotyczy-wszystkich-16-wojewodztw-i-6-upraw
- IUNG, raport o gospodarce wodnej: https://www.iung.pl/sir/SiR%2071(25)%20ISBN%20elektroniczny%20z%20ok%C5%82adk%C4%85.pdf
- Drenaż w Danii: https://link.springer.com/article/10.1007/s13280-021-01536-8
- Skjern: https://vbn.aau.dk/ws/files/145630831/10_years_after_the_largest_river_restoration_project_in_Northern_Europe.pdf ; https://old.ser-rrc.org/?p=8940
- Green Tripartite: https://www.en.kefm.dk/news/news-archive/2024/jul/the-danish-government-and-parties-in-“green-tripartite”-agree-on-a-ground-breaking-model-for-a-carbon-tax-on-food-and-agriculture-production
- SEGES Waterdrive: https://www.landbrugsinfo.dk/-/media/landbrugsinfo/public/8/2/8/am194570uk191004waterdrivecaseareaindenmark.pdf ; https://keep.eu/api/project-attachment/46085/get_file
- Mokradła ze zrębkami: https://landbrugsinfo.dk/public/1/7/4/miljotiltag_contructed_wetlands_with_woodchips
- Mapa drenaży (Aarhus): https://dcapub.au.dk/djfpublikation/djfpdf/DCArapport135.pdf
- SCALGO: https://scalgo.com/en-US/scalgo-live-documentation/country-specific/denmark

**Finansowanie**
- I.10.1.1: https://www.gov.pl/web/arimr/i1011-inwestycje-w-gospodarstwach-rolnych-zwiekszajace-konkurencyjnosc-dotacje
- Harmonogram naborów ARiMR 2026: https://www.gov.pl/attachment/07f00468-c1e5-43a4-918e-56de73f4e698
- FGR Plus: https://www.gov.pl/web/rolnictwo/fundusz-gwarancji-rolnych-plus ; https://www.gov.pl/attachment/0303d0d6-3dda-48fa-bd77-bd5c1c38dfd7
- I.10.4 (PODR): https://podr.pl/wp-content/uploads/2025/12/Ulotka_Dofinansowanie_na_poprawe_gospodarowania_woda.pdf
- Ekoschemat TUZ: https://wiescirolnicze.pl/ekoschemat-retencjonowanie-wody-na-trwalych-uzytkach-zielonych-omawiamy ; https://www.gov.pl/attachment/5b8e988c-33e8-4d41-bda7-82157d073500
- Torfowiska: https://www.gov.pl/attachment/bc53298a-c0a2-41b8-80e1-8a1a5616c7fe
- EPI: https://www.gov.pl/attachment/4409f804-48ef-4707-befe-75c3b8607791 ; https://www.gov.pl/web/arimr/interwencja-i135-wspolpraca-grup-operacyjnych-epi--zakres-wsparcie-przygotowawcze-w-ramach-ps-wpr-2023-2027
- NFOŚiGW Adaptacja: https://www.gramwzielone.pl/?p=20381695
- NFOŚiGW retencja: https://www.gov.pl/web/nfosigw/kazda-kropla-ma-znaczenie-nfosigw-finansuje-rozwiazania-retencyjne
- LIFE: https://www.gov.pl/web/nfosigw/po-pierwsze-srodowisko--start-naboru-wnioskow-na-wspolfinansowanie-projektow-life
- Mikroretencja: https://www.gov.pl/web/nfosigw/mikroretencja
- KPO B3.3.1: https://podr.pl/wp-content/uploads/2025/01/Zasady-udzielania-wsparcia-na-realizacje-przedsiewziec-w-ramach-inwestycji-B331.pdf ; https://api.sejm.gov.pl/sejm/term10/interpellations/13854/body ; https://api.sejm.gov.pl/sejm/term10/interpellations/13850/body
- Programy małej retencji (interpelacja): https://api.sejm.gov.pl/sejm/term10/interpellations/attachment/ATTDL5C5Z/i11494-o1.pdf

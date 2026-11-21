# Działki testowe (właściciel: zespół PRODUCT; korzysta zespół DATA)

Wszystkie identyfikatory sprawdzono 2026-11-21 przez `/api/parcel/resolve` (HTTP 200, ULDK GetParcelByIdOrNr).
Klasoużytki pochodzą z KIEG GUGiK (WMS GetFeatureInfo, warstwa `dzialki`, pole „Oznaczenie konturu”):
R = grunty orne, Ł = łąki, Ps = pastwiska, Br = grunty orne zabudowane, W = rowy, Ls = las, N = nieużytek.
„—” oznacza, że powiat nie publikuje klasoużytków w KIEG.

Działki wybierano, klikając pola na ortofotomapie (punkt środkiem pola → ULDK GetParcelByXY).
Jak dodać nową: patrz przepis na dole.

## Lista

| # | Identyfikator | Województwo / gmina | Pow. [ha] | Klasoużytki (EGiB) | Dlaczego ciekawa |
|---|---|---|---|---|---|
| 1 | `302504_5.0024.7` | wielkopolskie / Środa Wlkp. (Słupia Wielka) | 14.47 | RII, RIIIa, RIVa | dobre gleby, ale region najczęstszych susz (Wielkopolska); duże pole |
| 2 | `301907_5.0003.189/1` | wielkopolskie / Ujście (Jabłonowo) | 9.93 | RIVa, RV, RIIIb, LsVI | **lekkie gleby** (piaski, kompleksy żytnie), sąsiedztwo lasu – test maskowania `land_cover` |
| 3 | `181004_2.0003.939/5` | podkarpackie / Łańcut (Głuchów) | 0.36 | RIIIa | **luka mapy glebowej** (podkarpackie bez kompleksów) → fallback SoilGrids |
| 4 | `181105_2.0047.639/4` | podkarpackie / Mielec (Wola Mielecka) | 0.39 | PsIV, RIVa, RIVb | Kotlina Sandomierska, piaski; luka mapy glebowej; mała działka (wąski pas) |
| 5 | `061408_4.0006.828` | lubelskie / Nałęczów (Charz A) | 0.64 | RIIIb | **lessy, stoki** Płaskowyżu Nałęczowskiego – erozja, spływ powierzchniowy |
| 6 | `062014_2.0014.142` | lubelskie / Zamość (Mokre) | 1.68 | RII, RIIIa | lessy Działów Grabowieckich, bardzo dobre gleby, falisty teren |
| 7 | `060406_2.0136.AR_5.1077/6` | lubelskie / Trzeszczany (Nieledew) | 1.02 | RII, RIIIa | czarnoziemy hrubieszowskie; **identyfikator z arkuszem** (`AR_5`) – test parsera |
| 8 | `141310_2.0005.22` | mazowieckie / Wiśniewo (Kosiny Bartosowe) | 2.58 | RIVa, RIVb, RV | słabe gleby północnego Mazowsza |
| 9 | `100209_2.0004.140` | łódzkie / Oporów (Grotowice) | 3.78 | RIIIa, RIIIb | centralna Polska, obszar deficytu opadów |
| 10 | `160502_5.0003.1392` | opolskie / Krapkowice (Kórnica) | 0.52 | RIIIb, RIVa | Opolszczyzna, intensywne rolnictwo, cieplejszy klimat |
| 11 | `260102_2.0002.144` | świętokrzyskie / Gnojno (Bugaj) | 0.93 | RIVb, RV, PsIV, W/RV | rów (W) w obrębie działki – test reguły „zastawka na rowie” |
| 12 | `241107_2.0008.1930` | śląskie / Pietrowice Wielkie (Pawłów) | 6.16 | RII, RIIIa, RIIIb, RIVa, N | Płaskowyż Głubczycki / Kotlina Raciborska, lessy |
| 13 | `280202_2.0016.157` | warmińsko-mazurskie / Braniewo (Szyleny) | 3.35 | RIVa, PsIII | północ, chłodniejszy i wilgotniejszy klimat – kontrast |
| 14 | `321205_5.0005.167` | zachodniopomorskie / Pyrzyce (Turze) | 10.93 | ŁIV, ŁV | **trwały użytek zielony** (łąka) – test uprawy `tuz`, ekoschematu TUZ |
| 15 | `041409_5.0012.19/3` | kujawsko-pomorskie / Świecie (Morsk) | 6.88 | — | **dolina Wisły** – możliwa strefa zagrożenia powodziowego (ISOK) |
| 16 | `220907_5.0009.111` | pomorskie / Nowy Staw (Mirowo) | 1.39 | — | **Żuławy** – depresja, polder, gęsta sieć rowów melioracyjnych |
| 17 | `040706_5.0020.3309/3` | kujawsko-pomorskie / Kruszwica (Kobylniki) | 17.76 | — | Kujawy – najniższe opady w Polsce (< 500 mm), duże pole |
| – | `146505_8.0116.5` | mazowieckie / Warszawa | 0.42 | – | miejska, tylko test techniczny (nie rolna) |

## Pokrycie

- Województwa: 14 z 16 (brak: dolnośląskie, lubuskie, podlaskie, małopolskie – punkty testowe trafiały w las albo powiat nie zwraca danych; do uzupełnienia).
- Gleby: od klasy II (czarnoziemy, lessy) po V–VI (piaski); TUZ; mapa glebowa z luką (podkarpackie).
- Rzeźba: równiny (Kujawy, Wielkopolska), lessowe stoki (Nałęczów, Zamość), dolina Wisły, depresja Żuław.

## Przepis: jak dodać działkę

```bash
# 1. punkt na polu → identyfikator
curl -s "https://uldk.gugik.gov.pl/?request=GetParcelByXY&xy=17.20,52.22,4326&result=id,voivodeship,commune,parcel"
# 2. weryfikacja w aplikacji
curl -s "http://127.0.0.1:8000/api/parcel/resolve?id=302504_5.0024.7" | head -c 300
```

Klasoużytki: KIEG `https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow`,
`REQUEST=GetFeatureInfo&LAYERS=dzialki&QUERY_LAYERS=dzialki&INFO_FORMAT=text/html`.

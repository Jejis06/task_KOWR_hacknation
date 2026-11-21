from datetime import date, timedelta

import pytest

from app.connectors.drought import cdi_label, commune_teryt, parse_smsr_table, sma_value
from app.contracts.models import DailySeries
from app.science import smsr

HTML = """<h5 class="card-title">Gmina: Środa Wielkopolska; TERYT: 3025043</h5>
<h6 class="card-title">Kategoria gleby I</h6><table><thead><tr><th>Gatunek</th>
<th title="2024-03-21 - 2024-05-20">01</th><th title="2024-04-01 - 2024-05-31">02</th></tr></thead><tbody>
<tr><td class="s-name left bold">Zboża ozime</td><td class="s-susza">+</td><td class="s-brak">-</td></tr></tbody></table>
<h6 class="card-title">Kategoria gleby II</h6><table><thead><tr><th>Gatunek</th>
<th title="2024-03-21 - 2024-05-20">01</th><th title="2024-04-01 - 2024-05-31">02</th></tr></thead><tbody>
<tr><td class="s-name left bold">Zboża ozime</td><td class="s-brak">-</td><td>x</td></tr></tbody></table>
<h6 class="card-title">Kategoria gleby IV</h6><table><thead><tr><th>Gatunek</th>
<th title="2024-03-21 - 2024-05-20">01</th><th title="2024-04-01 - 2024-05-31">02</th></tr></thead><tbody>
<tr><td class="s-name left bold">Zboża ozime</td><td class="s-brak">-</td><td class="s-brak">-</td></tr></tbody></table>
<h6 class="card-title">Udział powierzchni zagrożonej suszą [%]</h6><table><thead><tr><th>G</th>
<th title="2024-03-21 - 2024-05-20">01</th><th title="2024-04-01 - 2024-05-31">02</th></tr></thead><tbody>
<tr><td class="s-name left bold">Zboża ozime</td><td>6.49</td><td>1.68</td></tr></tbody></table>"""


def test_parse_smsr_table():
    p = parse_smsr_table(HTML)
    assert p["commune"] == "Środa Wielkopolska"
    assert p["cats"]["I"]["zboża ozime"][0] == ("+", "2024-03-21", "2024-05-20")
    assert p["cats"]["II"]["zboża ozime"][1][0] == "x"
    assert p["cats"]["IV"]["zboża ozime"][0][0] == "-"      # „IV” nie może nadpisać kategorii „I”
    assert p["share"]["zboża ozime"][0][0] == "6.49"


def test_commune_teryt():
    assert commune_teryt("302504_5") == "3025043"
    assert commune_teryt("061201_2") == "0612012"
    assert commune_teryt("146505_8") == "1465011"
    assert commune_teryt(None) is None


def test_thresholds_loaded_and_evaluate():
    assert smsr.group_thresholds("zboża ozime", 1)[0] == -129
    assert smsr.group_thresholds("burak cukrowy", 1)[0] is None
    start = date(2019, 1, 1)
    ds = [start + timedelta(days=i) for i in range(365)]
    s = DailySeries(dates=ds, precip_mm=[0.5] * 365, tmax_c=[20] * 365, tmin_c=[10] * 365, et0_mm=[4.0] * 365)
    ev = smsr.evaluate_year(s, 2019, "zboża ozime", 2, date(2019, 7, 1))
    assert ev and all(e["drought"] for e in ev)        # KBW = −3,5 mm/d × 61 d ≈ −213 mm < progi kat. II
    assert ev[-1]["end"] <= "2019-07-01"                # brak „podglądania przyszłości”


def test_edo_color_mapping():
    assert cdi_label((220, 5, 12, 255)).startswith("alarm")
    assert cdi_label((0, 0, 0, 0)) == "brak suszy rolniczej"
    assert sma_value((179, 88, 6, 255))[1] == -2.0
    assert sma_value((200, 200, 200, 255)) is None


@pytest.mark.live
async def test_live_drought_smsr_srodka_2024():
    from app.connectors.drought import fetch_smsr_year
    p = await fetch_smsr_year(2024, "3025043")
    assert p and p["cats"]["I"]["zboża ozime"][0][0] == "+"

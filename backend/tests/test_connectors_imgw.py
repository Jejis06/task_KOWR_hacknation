import io
import zipfile
from datetime import date, timedelta

import pytest

from app.connectors import imgw
from app.contracts.models import DailySeries


def _zip(rows: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("s_d_330_2024.csv", "\n".join(rows).encode("cp1250"))
        zf.writestr("s_d_t_330_2024.csv", "ignored")
    return buf.getvalue()


def test_parse_zip_status_codes():
    rows = ['"352160330","POZNAŃ","2024","07","01",20,,10,,15,,8,,5.5,,"W"',
            '"352160330","POZNAŃ","2024","07","02",20,,10,,15,,8,,,"9",""',
            '"352160330","POZNAŃ","2024","07","03",20,,10,,15,,8,,,"8",""',
            '"352160999","INNA","2024","07","01",20,,10,,15,,8,,9.9,,"W"']
    out = imgw.parse_zip(_zip(rows), "352160330")
    assert out == {"2024-07-01": 5.5, "2024-07-02": 0.0, "2024-07-03": None}


def test_nearest_station_and_compare():
    st, dist = imgw.nearest_station(52.2, 17.25)
    assert st["name"].startswith("Poznań") and dist < 60
    start = date(2023, 1, 1)
    ds = [start + timedelta(days=i) for i in range(365)]
    s = DailySeries(dates=ds, precip_mm=[1.2] * 365, tmax_c=[0] * 365, tmin_c=[0] * 365, et0_mm=[1] * 365)
    pr = {d: 1.0 for d in ds}
    c = imgw.compare(s, pr, ds[-1])
    assert c["season_bias_pct"] == 20.0 and c["station_last_30d_precip_mm"] == 30.0


@pytest.mark.live
async def test_live_imgw_poznan():
    st, _ = imgw.nearest_station(52.4, 16.9)
    pr = await imgw.station_precip(st, date(2023, 6, 1), date(2023, 6, 30))
    assert len(pr) == 30

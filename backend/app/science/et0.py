"""FAO-56 Penman–Monteith – dobowa ewapotranspiracja wskaźnikowa ET0 [mm/d].

Źródło: Allen, Pereira, Raes, Smith (1998/2025), FAO Irrigation and Drainage Paper 56, rów. 6, 21, 37–39.
Używane, gdy dostawca meteo nie podaje ET0 (np. NASA POWER).
"""
from __future__ import annotations

import math
from datetime import date


def et0_penman_monteith(d: date, lat_deg: float, elev_m: float, tmax: float, tmin: float,
                        rh_mean: float, u2: float, rs_mj: float) -> float:
    tmean = (tmax + tmin) / 2
    p = 101.3 * ((293 - 0.0065 * elev_m) / 293) ** 5.26                 # kPa
    gamma = 0.000665 * p
    es_t = lambda t: 0.6108 * math.exp(17.27 * t / (t + 237.3))         # noqa: E731
    es = (es_t(tmax) + es_t(tmin)) / 2
    ea = es * rh_mean / 100
    delta = 4098 * es_t(tmean) / (tmean + 237.3) ** 2
    # promieniowanie
    j = d.timetuple().tm_yday
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365)
    dec = 0.409 * math.sin(2 * math.pi * j / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(dec))))
    ra = 24 * 60 / math.pi * 0.0820 * dr * (ws * math.sin(phi) * math.sin(dec)
                                            + math.cos(phi) * math.cos(dec) * math.sin(ws))
    rso = (0.75 + 2e-5 * elev_m) * ra
    rns = 0.77 * rs_mj
    sigma = 4.903e-9
    rnl = sigma * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2) * (0.34 - 0.14 * math.sqrt(max(ea, 0))) \
        * (1.35 * min(rs_mj / rso, 1.0) - 0.35) if rso > 0 else 0.0
    rn = rns - rnl
    et0 = (0.408 * delta * rn + gamma * 900 / (tmean + 273) * u2 * (es - ea)) / (delta + gamma * (1 + 0.34 * u2))
    return max(0.0, et0)

"""FAO-56 (Allen i in. 1998, FAO Irrigation and Drainage Paper 56) – bilans wody w strefie korzeni i stres wodny.

Implementacja własna równań (same wzory nie podlegają prawu autorskiemu); w repo NIE ma tekstu ani tabel książki.
Numery równań wg FAO-56:
- równ. 62  – korekta Kc mid/end do klimatu (wiatr u2, minimalna wilgotność RHmin, wysokość roślin h),
- rozdz. 8, tab. 22 – korekta frakcji p do bieżącego ETc: p = p_tab + 0,04·(5 − ETc), w granicach 0,1–0,8,
- równ. 82–83 – TAW = (θFC − θWP)·Zr (u nas: zapas wody dostępnej na 1 m × Zr), RAW = p·TAW,
- równ. 84  – Ks = (TAW − Dr) / ((1 − p)·TAW) dla Dr > RAW, inaczej 1,
- równ. 81  – ETc adj = Ks·Kc·ET0,
- równ. 85–86, 88 – dobowy bilans: Dr,i = Dr,i−1 − (P − RO)i − Ii − CRi + ETc,i + DPi, 0 ≤ Dr ≤ TAW;
  nadwyżka ponad pojemność polową odpływa tego samego dnia (DP), co w praktyce daje dolne ograniczenie Dr ≥ 0,
- równ. 90  – 1 − Ya/Ym = Ky·(1 − ETc adj/ETc) (Ky sezonowe z tab. 24, za FAO-33),
- rozdz. 9 (mulcz organiczny) – parowanie z gleby mniejsze o ok. 5% na każde 10% powierzchni okrytej mulczem.

Uproszczenia (opisane w `limitations` analizy): RO = 0 (spływ powierzchniowy pomijamy), CR = 0 (bez podsiąku
z wód gruntowych), start bilansu z Dr = 0 (gleba w pojemności polowej po zimie – FAO-56 zaleca start po obfitym
deszczu lub nawadnianiu).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


def kc_climate_adjust(kc_tab: float, u2: float = 2.0, rh_min: float = 45.0, h: float = 1.0) -> float:
    """Równ. 62: Kc = Kc(tab) + [0,04(u2 − 2) − 0,004(RHmin − 45)]·(h/3)^0,3 (dla Kc ≥ 0,45)."""
    if kc_tab < 0.45:
        return kc_tab
    u2 = min(6.0, max(1.0, u2))
    rh_min = min(80.0, max(20.0, rh_min))
    h = min(10.0, max(0.1, h))
    return round(kc_tab + (0.04 * (u2 - 2) - 0.004 * (rh_min - 45)) * (h / 3) ** 0.3, 3)


def p_adjust(p_tab: float, etc_mm_d: float) -> float:
    """Tab. 22 (przypis): p = p_tab + 0,04·(5 − ETc), ograniczone do 0,1–0,8."""
    return min(0.8, max(0.1, p_tab + 0.04 * (5.0 - etc_mm_d)))


def taw_mm(awc_mm_per_m: float, root_depth_m: float) -> float:
    """Równ. 82 (z zapasem wody dostępnej podanym na 1 m gleby)."""
    return awc_mm_per_m * root_depth_m


def ks_coefficient(dr: float, taw: float, p: float) -> float:
    """Równ. 84."""
    raw = p * taw
    if dr <= raw or taw <= 0:
        return 1.0
    return max(0.0, (taw - dr) / ((1.0 - p) * taw))


def yield_loss_fraction(ky: float, eta: float, etc: float) -> float:
    """Równ. 90: 1 − Ya/Ym = Ky·(1 − ETa/ETc)."""
    if etc <= 0:
        return 0.0
    return max(0.0, min(1.0, ky * (1.0 - eta / etc)))


def mulch_evaporation_saving(soil_evap_mm: float, cover_fraction: float) -> float:
    """Rozdz. 9: parowanie z gleby mniejsze o ~5% na każde 10% powierzchni okrytej mulczem organicznym."""
    return soil_evap_mm * 0.5 * max(0.0, min(1.0, cover_fraction))


@dataclass
class DayState:
    day: date
    dr: float          # wyczerpanie wody w strefie korzeni na koniec dnia [mm]
    raw: float
    taw: float
    ks: float
    etc: float         # ETc bez stresu [mm]
    eta: float         # ETc adj [mm]
    forecast: bool = False


@dataclass
class BalanceResult:
    days: list[DayState] = field(default_factory=list)

    @property
    def last(self) -> DayState | None:
        return next((d for d in reversed(self.days) if not d.forecast), None)

    def season_ratio(self) -> float | None:
        obs = [d for d in self.days if not d.forecast]
        etc = sum(d.etc for d in obs)
        return round(sum(d.eta for d in obs) / etc, 3) if etc > 0 else None

    def first_stress(self) -> DayState | None:
        return next((d for d in self.days if d.forecast and d.dr > d.raw), None)


def root_zone_balance(days: list[tuple[date, float | None, float | None, float, bool]], awc_mm_per_m: float,
                      root_depth_m: float, p_tab: float, dr0: float = 0.0) -> BalanceResult:
    """Dobowy bilans (równ. 85–86, 88) z Ks (84) i ETc adj (81).

    `days` = [(dzień, opad mm, ET0 mm, Kc, czy_prognoza)]; brakujące P/ET0 traktujemy jako 0 (bez zysku i straty).
    """
    taw = taw_mm(awc_mm_per_m, root_depth_m)
    dr = min(max(0.0, dr0), taw)
    out = BalanceResult()
    for d, p, et0, kc, fc in days:
        p = p or 0.0
        et0 = et0 or 0.0
        etc = kc * et0
        pp = p_adjust(p_tab, etc)
        ks = ks_coefficient(dr, taw, pp)
        eta = ks * etc
        dr = dr - p + eta              # RO = 0, I = 0, CR = 0
        dr = min(taw, max(0.0, dr))    # nadwyżka → DP (równ. 88), limit TAW (równ. 86)
        out.days.append(DayState(day=d, dr=round(dr, 1), raw=round(pp * taw, 1), taw=round(taw, 1),
                                 ks=round(ks, 3), etc=round(etc, 2), eta=round(eta, 2), forecast=fc))
    return out

"""FAO-56: równania 62, 84, 85–86, 90 i reguła mulczu – wartości liczone ręcznie."""
from datetime import date, timedelta

from app.science import fao56


def test_kc_climate_adjust_eq62():
    assert fao56.kc_climate_adjust(1.2, 2.0, 45.0, 1.0) == 1.2          # warunki standardowe → bez zmian
    assert fao56.kc_climate_adjust(1.2, 4.0, 30.0, 3.0) > 1.2           # wietrznie i sucho → Kc większe
    assert fao56.kc_climate_adjust(0.3, 4.0, 30.0, 3.0) == 0.3          # Kc < 0,45 – bez korekty


def test_ks_eq84_and_yield_eq90():
    assert fao56.ks_coefficient(50, 200, 0.5) == 1.0                    # Dr < RAW
    assert abs(fao56.ks_coefficient(150, 200, 0.5) - 0.5) < 1e-9       # (200−150)/(0,5·200)
    assert abs(fao56.yield_loss_fraction(1.25, 0.8, 1.0) - 0.25) < 1e-9


def test_root_zone_balance_limits():
    d0 = date(2026, 5, 1)
    days = [(d0 + timedelta(days=i), 0.0, 5.0, 1.0, False) for i in range(60)]
    b = fao56.root_zone_balance(days, awc_mm_per_m=100, root_depth_m=1.0, p_tab=0.5)
    assert all(0 <= x.dr <= x.taw for x in b.days)                       # równ. 86
    assert b.days[-1].ks < 1 and b.season_ratio() < 1
    wet = [(d0, 100.0, 5.0, 1.0, False)]
    assert fao56.root_zone_balance(wet, 100, 1.0, 0.5).days[0].dr == 0   # nadwyżka → DP (równ. 88)


def test_mulch_rule():
    assert fao56.mulch_evaporation_saving(40.0, 0.5) == 10.0            # 50% okrycia → −25%

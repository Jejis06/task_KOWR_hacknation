"""Analiza rzeźby z NMT (numpy/scipy, bez GPL): spadek, ekspozycja, TPI, Priority-Flood, D8, TWI.

Siatka: tablica `z[row, col]`, wiersz 0 = północ, komórka `cell` m. NaN = brak danych.
Algorytmy:
- Priority-Flood (Barnes, Lehman, Mulla 2014) – wypełnianie zagłębień; wariant +ε daje spadek na płaskich
  powierzchniach, żeby D8 zawsze miał kierunek.
- D8 (O'Callaghan & Mark 1984) – akumulacja przepływu w kolejności malejącej wysokości.
- TWI = ln(a / tan β), a = powierzchnia zlewni na jednostkę szerokości (Beven & Kirkby 1979).
"""
from __future__ import annotations

import heapq

import numpy as np

# 8 sąsiadów: (dr, dc)
NB = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
NB_DIST = np.array([1, 2 ** 0.5, 1, 2 ** 0.5, 1, 2 ** 0.5, 1, 2 ** 0.5])
ASPECT_8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def fill_nan(z: np.ndarray) -> np.ndarray:
    """Uzupełnia pojedyncze braki średnią sąsiadów (iteracyjnie); całkowite braki → min."""
    from scipy import ndimage
    z = z.copy()
    for _ in range(10):
        m = np.isnan(z)
        if not m.any():
            break
        zz = np.where(m, 0, z)
        w = ndimage.uniform_filter((~m).astype(float), 3, mode="nearest")
        s = ndimage.uniform_filter(zz, 3, mode="nearest")
        with np.errstate(invalid="ignore", divide="ignore"):
            est = s / w
        z[m & (w > 0)] = est[m & (w > 0)]
    if np.isnan(z).any():
        z[np.isnan(z)] = np.nanmin(z)
    return z


def slope_aspect(z: np.ndarray, cell: float) -> tuple[np.ndarray, np.ndarray]:
    """Spadek [°] i ekspozycja [° od N, zgodnie z ruchem wskazówek] (gradient centralny)."""
    dz_dr, dz_dc = np.gradient(z, cell)          # dr: w dół = na południe; dc: w prawo = na wschód
    dzdx, dzdy = dz_dc, -dz_dr                    # x = wschód, y = północ
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360) % 360  # kierunek spadku (downslope)
    return slope, aspect


def dominant_aspect(aspect: np.ndarray, slope: np.ndarray, mask: np.ndarray) -> str | None:
    sel = mask & (slope > 1.0)
    if sel.sum() < max(3, 0.1 * mask.sum()):
        return None  # teren płaski – ekspozycja bez znaczenia
    a = np.radians(aspect[sel])
    mean = (np.degrees(np.arctan2(np.sin(a).mean(), np.cos(a).mean())) + 360) % 360
    return ASPECT_8[int(((mean + 22.5) % 360) // 45)]


def tpi(z: np.ndarray, cell: float, radius_m: float) -> np.ndarray:
    """Topographic Position Index: wysokość minus średnia w kwadratowym oknie ~2·radius."""
    from scipy import ndimage
    size = max(3, int(2 * radius_m / cell) | 1)
    return z - ndimage.uniform_filter(z, size=size, mode="nearest")


def priority_flood(z: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    """Wypełnia zagłębienia; krawędź siatki = ujście. eps > 0 → minimalny spadek na wypełnionych płaskich."""
    rows, cols = z.shape
    filled = z.copy()
    closed = np.zeros(z.shape, dtype=bool)
    heap: list[tuple[float, int, int]] = []
    for r in range(rows):
        for c in (0, cols - 1):
            if not closed[r, c]:
                closed[r, c] = True
                heapq.heappush(heap, (filled[r, c], r, c))
    for c in range(cols):
        for r in (0, rows - 1):
            if not closed[r, c]:
                closed[r, c] = True
                heapq.heappush(heap, (filled[r, c], r, c))
    while heap:
        h, r, c = heapq.heappop(heap)
        for dr, dc in NB:
            rr, cc = r + dr, c + dc
            if 0 <= rr < rows and 0 <= cc < cols and not closed[rr, cc]:
                closed[rr, cc] = True
                if filled[rr, cc] <= h:
                    filled[rr, cc] = h + eps
                heapq.heappush(heap, (filled[rr, cc], rr, cc))
    return filled


def d8_accumulation(zf: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kierunek D8 (indeks 0–7, -1 = ujście na brzegu) i akumulacja (liczba komórek, z własną)."""
    rows, cols = zf.shape
    pad = np.pad(zf, 1, mode="edge")
    drops = np.empty((8, rows, cols))
    for k, (dr, dc) in enumerate(NB):
        nbz = pad[1 + dr:1 + dr + rows, 1 + dc:1 + dc + cols]
        drops[k] = (zf - nbz) / NB_DIST[k]
    # brzeg: sąsiad poza siatką → brak (edge-pad dałby 0)
    drops[:, 0, :][[0, 1, 7]] = -np.inf
    drops[:, -1, :][[3, 4, 5]] = -np.inf
    drops[:, :, 0][[5, 6, 7]] = -np.inf
    drops[:, :, -1][[1, 2, 3]] = -np.inf
    fdir = np.argmax(drops, axis=0)
    has = np.max(drops, axis=0) > 0
    fdir = np.where(has, fdir, -1)
    acc = np.ones(zf.shape)
    order = np.argsort(zf, axis=None)[::-1]
    dr_arr = np.array([d[0] for d in NB]); dc_arr = np.array([d[1] for d in NB])
    fd_flat = fdir.ravel(); acc_flat = acc.ravel()
    for idx in order:
        k = fd_flat[idx]
        if k < 0:
            continue
        r, c = divmod(int(idx), cols)
        acc_flat[(r + dr_arr[k]) * cols + (c + dc_arr[k])] += acc_flat[idx]
    return fdir, acc


def twi(acc: np.ndarray, slope_deg: np.ndarray, cell: float) -> np.ndarray:
    a = acc * cell  # (komórki · cell²) / cell = powierzchnia na jednostkę szerokości
    tanb = np.maximum(np.tan(np.radians(slope_deg)), 0.001)
    return np.log(a / tanb)


def classify_position(tpi_m: float, tpi_sd: float, slope_mean: float, depression_share: float) -> tuple[str, str]:
    """Pozycja w rzeźbie (Weiss 2001, progi dostosowane do płaskiej Polski: min. 0,3 m / 1 m)."""
    t1 = min(max(0.3, 0.5 * tpi_sd), 1.5)
    t2 = min(max(1.0, 1.0 * tpi_sd), 3.0)
    if depression_share >= 0.3 or tpi_m < -t2:
        return "depression", "zagłębienie (dołek) – woda spływa tu z otoczenia"
    if tpi_m > t2:
        return "hilltop", "górka (wzniesienie) – woda szybko odpływa"
    if tpi_m > t1:
        return "upper_slope", "górna część stoku – woda raczej odpływa"
    if tpi_m < -t1:
        return "valley", "obniżenie / dolina – woda dopływa z wyżej położonych terenów"
    if slope_mean >= 2.0:
        return "mid_slope", "stok – woda spływa przez działkę"
    return "flat", "teren płaski"

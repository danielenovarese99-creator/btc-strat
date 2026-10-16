"""
Indicatori replicati in modo fedele a Pine Script v6 (TradingView).

Dettagli che contano per ottenere gli stessi segnali di TradingView:
- ta.ema usa come seme la SMA delle prime `length` barre valide (non il primo valore).
- ta.stdev e' la deviazione standard di POPOLAZIONE (divide per n, non n-1).
- ta.alma NON arrotonda l'offset (floor=false); il peso piu' alto va alle barre recenti.
- ta.linreg(src, len, 0) e' il valore della retta di regressione sull'ultima barra.
- crossover/crossunder: a > b (a < b) adesso e a <= b (a >= b) alla barra precedente.
"""

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def stdev_pop(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).std(ddof=0)


def ema(s: pd.Series, n: int) -> pd.Series:
    """Equivalente a ta.ema di Pine: seme = SMA delle prime n barre valide."""
    vals = s.to_numpy(dtype=float)
    seed = s.rolling(n).mean().to_numpy()
    out = np.full(len(vals), np.nan)
    alpha = 2.0 / (n + 1)
    prev = np.nan
    for i in range(len(vals)):
        x = vals[i]
        if np.isnan(prev):
            if not np.isnan(seed[i]):
                prev = seed[i]
                out[i] = prev
        else:
            if np.isnan(x):
                prev = np.nan
            else:
                prev = alpha * x + (1 - alpha) * prev
                out[i] = prev
    return pd.Series(out, index=s.index)


def dema(s: pd.Series, n: int) -> pd.Series:
    e1 = ema(s, n)
    e2 = ema(e1, n)
    return 2 * e1 - e2


def tema(s: pd.Series, n: int) -> pd.Series:
    e1 = ema(s, n)
    e2 = ema(e1, n)
    e3 = ema(e2, n)
    return 3 * (e1 - e2) + e3


def roc(s: pd.Series, n: int) -> pd.Series:
    prev = s.shift(n)
    return 100.0 * (s - prev) / prev


def highest(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).max()


def lowest(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).min()


def median(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).median()


def linreg(s: pd.Series, n: int, offset: int = 0) -> pd.Series:
    """ta.linreg: valore della regressione lineare (x=0 la barra piu' vecchia della finestra)."""
    vals = s.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    if len(vals) < n:
        return pd.Series(out, index=s.index)
    win = sliding_window_view(vals, n)
    x = np.arange(n, dtype=float)
    xm = x.mean()
    dx = x - xm
    ym = win.mean(axis=1)
    slope = (win * dx).sum(axis=1) / (dx ** 2).sum()
    out[n - 1:] = ym + slope * ((n - 1 - offset) - xm)
    return pd.Series(out, index=s.index)


def alma(s: pd.Series, n: int, offset: float, sigma: float) -> pd.Series:
    """ta.alma(series, length, offset, sigma) senza floor."""
    vals = s.to_numpy(dtype=float)
    out = np.full(len(vals), np.nan)
    if len(vals) < n:
        return pd.Series(out, index=s.index)
    m = offset * (n - 1)
    sc = n / sigma
    w = np.exp(-((np.arange(n) - m) ** 2) / (2 * sc ** 2))
    w = w / w.sum()
    win = sliding_window_view(vals, n)  # colonna 0 = barra piu' vecchia
    out[n - 1:] = win @ w
    return pd.Series(out, index=s.index)


def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a < b) & (a.shift(1) >= b.shift(1))

"""
Logica della strategia "1349_BTC": segnali + macchina a stati (stop-and-reverse).

Condizioni di ingresso (identiche allo script Pine, valutate alla chiusura della barra):
  LONG  = oscillatore > 0  AND  supertrend-ALMA rialzista  AND  (EMD bull OR LSMA in salita)   [se non gia' long]
  SHORT = oscillatore < signal AND crossunder(close, mediana) AND (EMD bear OR LSMA in discesa) [se non gia' short]
Nessuno stop e nessun target: la posizione cambia solo quando scatta il segnale opposto.
Il sizing su TradingView e' 100% dell'equity senza leva (qui: 1x il capitale assegnato).
"""

import numpy as np
import pandas as pd

import config as cfg
import indicators as ind


def _source(df: pd.DataFrame, name: str) -> pd.Series:
    if name == "hlc3":
        return (df["high"] + df["low"] + df["close"]) / 3.0
    if name == "hlcc4":
        return (df["high"] + df["low"] + 2 * df["close"]) / 4.0
    if name == "close":
        return df["close"]
    raise ValueError(f"CALC_SOURCE non supportato: {name}")


def _emd_direction(close: pd.Series) -> pd.Series:
    """EMD_Trend: direzione persistente (+1/-1) dopo crossover/crossunder delle bande."""
    avg = ind.dema(close, cfg.EMD_LENGTH)
    emd = ind.ema((close - avg).abs(), cfg.EMD_LENGTH)
    avg_p = avg + emd * cfg.EMD_MULT
    avg_m = avg - emd * cfg.EMD_MULT
    up = ind.crossover(close, avg_p).to_numpy()
    dn = ind.crossunder(close, avg_m).to_numpy()
    direction = np.zeros(len(close))
    d = 0
    for i in range(len(close)):
        if up[i]:
            d = 1
        elif dn[i]:
            d = -1
        direction[i] = d
    return pd.Series(direction, index=close.index)


def _alma_supertrend(close: pd.Series, sd_src: pd.Series) -> pd.Series:
    """
    Porting letterale della funzione st() dello script. Attenzione: come nello Pine originale,
    le bande sono centrate sull'ALMA del close ma la deviazione standard e' calcolata sulla
    sorgente del ROC (hlc3), perche' st() viene chiamata con `src`.
    Ritorna direction (-1 = rialzista, +1 = ribassista).
    """
    alma_v = ind.alma(close, cfg.ALMA_LEN, cfg.ALMA_OFFSET, cfg.ALMA_SIGMA).to_numpy()
    sd = ind.stdev_pop(sd_src, cfg.ST_SD_LEN).to_numpy()
    c = close.to_numpy()
    n = len(c)

    ub_final = np.full(n, np.nan)
    lb_final = np.full(n, np.nan)
    st_final = np.full(n, np.nan)
    direction = np.full(n, np.nan)

    def nz(x):
        return 0.0 if np.isnan(x) else x

    for i in range(n):
        upper = alma_v[i] + cfg.ST_FACTOR * sd[i]
        lower = alma_v[i] - cfg.ST_FACTOR * sd[i]
        prev_ub = nz(ub_final[i - 1]) if i > 0 else 0.0
        prev_lb = nz(lb_final[i - 1]) if i > 0 else 0.0
        c_prev = c[i - 1] if i > 0 else np.nan

        ub = upper if (upper < prev_ub or c_prev > prev_ub) else prev_ub
        lb = lower if (lower > prev_lb or c_prev < prev_lb) else prev_lb

        prev_st = st_final[i - 1] if i > 0 else np.nan
        sd_prev_na = (i == 0) or np.isnan(sd[i - 1])
        if sd_prev_na:
            d = 1
        elif prev_st == prev_ub:
            d = -1 if c[i] > ub else 1
        else:
            d = 1 if c[i] < lb else -1

        ub_final[i], lb_final[i], direction[i] = ub, lb, d
        st_final[i] = lb if d == -1 else ub

    return pd.Series(direction, index=close.index)


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """df: colonne time, open, high, low, close, volume (barre CHIUSE, ordine cronologico)."""
    out = df.copy().reset_index(drop=True)
    close = out["close"]
    src = _source(out, cfg.CALC_SOURCE)

    # --- Oscillatore (ROC normalizzato pesato sulla differenza dalla TEMA) ---
    roc = ind.roc(src, cfg.ROC_LEN)
    rng = ind.highest(roc, cfg.ROC_LEN) - ind.lowest(roc, cfg.ROC_LEN)
    norm_roc = ((roc - ind.lowest(roc, cfg.ROC_LEN)) / rng).replace([np.inf, -np.inf], np.nan)
    base_ma = ind.tema(src, cfg.MA_LEN)
    rwma = base_ma + norm_roc * (src - base_ma)
    z = (rwma - ind.sma(rwma, cfg.ROC_LEN)) / ind.stdev_pop(rwma, cfg.ROC_LEN)
    oscillator = z.replace([np.inf, -np.inf], np.nan)
    signal = ind.ema(oscillator, cfg.SIG_LEN)

    # --- Filtri ---
    emd_dir = _emd_direction(close)
    emd_bull = emd_dir.shift(1) > 0          # come dir[1] > 0 nello Pine
    emd_bear = emd_dir.shift(1) < 0
    lsma = ind.linreg(close, cfg.LSMA_LEN, cfg.LSMA_OFFSET)
    lsma_bull = lsma > lsma.shift(1)
    lsma_bear = lsma < lsma.shift(1)
    st_dir = _alma_supertrend(close, src)
    long_alma = st_dir < 0
    med = ind.median(close, cfg.MEDIAN_LEN)
    med_bear = ind.crossunder(close, med)

    out["oscillator"] = oscillator
    out["signal"] = signal
    out["emd_dir"] = emd_dir
    out["st_dir"] = st_dir
    out["long_cond"] = ((oscillator > 0) & long_alma & (emd_bull | lsma_bull)).fillna(False)
    out["short_cond"] = ((oscillator < signal) & med_bear & (emd_bear | lsma_bear)).fillna(False)
    return out


def run_state_machine(sig: pd.DataFrame, start) -> pd.Series:
    """
    Posizione (+1 long, -1 short, 0 flat) DOPO la chiusura di ogni barra.
    Replica gli `if` dello script: entrambi usano la posizione di inizio barra (gli ordini
    si eseguono a fine barra con process_orders_on_close), e se scattano entrambi vince lo short.
    """
    start_ts = pd.Timestamp(start, tz="UTC")
    in_range = (sig["time"] >= start_ts).to_numpy()
    lc = sig["long_cond"].to_numpy()
    sc = sig["short_cond"].to_numpy()
    pos = 0
    out = np.zeros(len(sig), dtype=int)
    for i in range(len(sig)):
        old = pos
        if in_range[i]:
            if lc[i] and old <= 0:
                pos = 1
            if sc[i] and old >= 0:
                pos = -1
        out[i] = pos
    return pd.Series(out, index=sig.index, name="position")

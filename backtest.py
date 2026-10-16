"""
Backtest della strategia 1349_BTC, stesso modello di TradingView:
ordini alla chiusura della barra, 100% dell'equity, senza leva, stop-and-reverse.

Uso:
    python backtest.py --csv btc_daily.csv            # dati esportati da TradingView (consigliato per il confronto)
    python backtest.py                                # candele BTC da Hyperliquid
    python backtest.py --start 2023-01-01 --fee 0.00045
Output: trades.csv, equity_curve.csv e un riepilogo a video.
"""

import argparse

import numpy as np
import pandas as pd

import config as cfg
import data as data_mod
import strategy as strat


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=None, help="CSV con time,open,high,low,close (es. export TradingView)")
    p.add_argument("--start", default=cfg.STRATEGY_START, help="data di inizio trading (UTC), default 2023-01-01")
    p.add_argument("--fee", type=float, default=0.0,
                   help="commissione per lato come frazione del notional (es. 0.00045 = 0,045%%). Default 0 come TradingView")
    return p.parse_args()


def run(df: pd.DataFrame, start: str, fee: float = 0.0):
    sig = strat.compute_signals(df)
    pos = strat.run_state_machine(sig, start)
    sig["position"] = pos

    close = sig["close"].to_numpy()
    n = len(sig)
    # Come su TradingView la quantita' si fissa all'ingresso (100% dell'equity di quel momento) e
    # NON viene ribilanciata ogni giorno: per uno short l'equity e' eq_ingresso * (1 - (P/P_ingresso - 1)).
    eq = np.ones(n)
    start_ts = pd.Timestamp(start, tz="UTC")
    first = int(np.argmax((sig["time"] >= start_ts).to_numpy()))
    p = pos.to_numpy()
    eq_entry, px_entry, side = 1.0, close[first], 0
    for i in range(first, n):
        prev = p[i - 1] if i > first else 0
        marked = eq_entry * (1.0 + side * (close[i] / px_entry - 1.0)) if side != 0 else eq_entry
        if p[i] != prev:                       # cambio posizione alla chiusura della barra i
            marked *= 1.0 - fee * abs(p[i] - prev)
            eq_entry, px_entry, side = marked, close[i], int(p[i])
        eq[i] = marked
    sig["equity"] = eq

    # --- lista trade ---
    trades = []
    cur = None
    for i in range(first, n):
        if p[i] != (p[i - 1] if i > first else 0):
            if cur is not None:
                cur["exit_time"], cur["exit_price"] = sig["time"].iloc[i], close[i]
                trades.append(cur)
                cur = None
            if p[i] != 0:
                cur = {"side": "long" if p[i] > 0 else "short", "open": False,
                       "entry_time": sig["time"].iloc[i], "entry_price": close[i]}
    if cur is not None:
        cur["exit_time"], cur["exit_price"] = pd.NaT, close[-1]   # ancora aperto, valutato all'ultima chiusura
        cur["open"] = True
        trades.append(cur)
    tr = pd.DataFrame(trades)
    if not tr.empty:
        side = np.where(tr["side"] == "long", 1.0, -1.0)
        tr["return_pct"] = side * (tr["exit_price"] / tr["entry_price"] - 1.0) * 100.0
        tr["open"] = tr["open"].astype(bool)
    return sig, tr, first


def summary(sig: pd.DataFrame, tr: pd.DataFrame, first: int, fee: float):
    eq = sig["equity"].iloc[first:]
    total = (eq.iloc[-1] - 1) * 100
    dd = (eq / eq.cummax() - 1).min() * 100
    days = (sig["time"].iloc[-1] - sig["time"].iloc[first]).days
    cagr = ((eq.iloc[-1]) ** (365.0 / days) - 1) * 100 if days > 0 and eq.iloc[-1] > 0 else float("nan")
    bh = (sig["close"].iloc[-1] / sig["close"].iloc[first] - 1) * 100
    closed = tr[~tr["open"]] if not tr.empty else tr

    print("=" * 62)
    print("RIEPILOGO BACKTEST - 1349_BTC (long & short, stop-and-reverse)")
    print("=" * 62)
    print(f"Periodo:               {sig['time'].iloc[first].date()} -> {sig['time'].iloc[-1].date()} ({days} giorni)")
    print(f"Commissioni per lato:  {fee*100:.4f}%")
    print(f"Rendimento totale:     {total:+.1f}%   (include l'eventuale trade ancora aperto)")
    if not closed.empty:
        closed_comp = (np.prod(1 + closed["return_pct"] / 100) - 1) * 100
        print(f"Solo trade chiusi:     {closed_comp:+.1f}%")
    print(f"Rendimento annuo:      {cagr:+.1f}%")
    print(f"Max drawdown (chiusure): {dd:.1f}%")
    print(f"Buy & hold stesso periodo: {bh:+.1f}%")
    if not tr.empty:
        w = closed[closed["return_pct"] > 0]
        l = closed[closed["return_pct"] <= 0]
        pf = w["return_pct"].sum() / abs(l["return_pct"].sum()) if len(l) and l["return_pct"].sum() != 0 else float("nan")
        print(f"N trade (chiusi):      {len(closed)}   (long {int((closed['side']=='long').sum())}, short {int((closed['side']=='short').sum())})")
        print(f"Win rate:              {len(w)/max(len(closed),1)*100:.1f}%")
        print(f"Vincita/perdita media: {w['return_pct'].mean():+.1f}% / {l['return_pct'].mean():+.1f}%")
        print(f"Profit factor:         {pf:.2f}")
        for s in ("long", "short"):
            x = closed[closed["side"] == s]
            if len(x):
                print(f"  {s:5s}: {len(x)} trade, rendimento composto {(np.prod(1 + x['return_pct']/100) - 1)*100:+.1f}%, "
                      f"win rate {(x['return_pct']>0).mean()*100:.0f}%")
        if tr["open"].any():
            o = tr[tr["open"]].iloc[0]
            print(f"Posizione attuale:     {o['side'].upper()} dal {o['entry_time'].date()} a {o['entry_price']:.2f} "
                  f"({o['return_pct']:+.1f}% non realizzato)")
    print("=" * 62)


def main():
    args = parse_args()
    df = data_mod.load_csv(args.csv) if args.csv else data_mod.fetch_hyperliquid()
    print(f"Dati: {len(df)} barre giornaliere, dal {df['time'].iloc[0].date()} al {df['time'].iloc[-1].date()}")
    if df["time"].iloc[0] > pd.Timestamp(args.start, tz="UTC") - pd.Timedelta(days=400):
        print("[WARN] storico precedente alla data di inizio molto corto: gli indicatori con memoria "
              "(supertrend, EMD, EMA lunghe) non convergono come su TradingView. Meglio >= 1 anno di warm-up.")
    sig, tr, first = run(df, args.start, args.fee)
    sig[["time", "close", "oscillator", "signal", "long_cond", "short_cond", "position", "equity"]].to_csv(
        "equity_curve.csv", index=False)
    if not tr.empty:
        tr.to_csv("trades.csv", index=False)
        print("Salvati: trades.csv, equity_curve.csv")
    summary(sig, tr, first, args.fee)


if __name__ == "__main__":
    main()

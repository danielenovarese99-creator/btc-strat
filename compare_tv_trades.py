"""
Confronta i trade di questo backtest (trades.csv) con la "List of trades" esportata da TradingView
(Strategy Tester -> Lista dei trade -> Esporta). Serve a vedere se le entrate coincidono.

    python compare_tv_trades.py tv_trades.csv [trades.csv]
"""

import sys

import pandas as pd


def load_tv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    type_col = next(c for k, c in cols.items() if k.startswith("type") or k.startswith("tipo"))
    date_col = next(c for k, c in cols.items() if "date" in k or "data" in k)
    price_col = next(c for k, c in cols.items() if "price" in k or "prezzo" in k)
    e = df[df[type_col].str.lower().str.contains("entry|entrata|ingresso")].copy()
    e["side"] = e[type_col].str.lower().apply(lambda t: "short" if "short" in t else "long")
    e["time"] = pd.to_datetime(e[date_col]).dt.normalize()
    e["price"] = e[price_col].astype(str).str.replace(",", "").astype(float)
    return e[["time", "side", "price"]].reset_index(drop=True)


def main():
    tv = load_tv(sys.argv[1])
    mine = pd.read_csv(sys.argv[2] if len(sys.argv) > 2 else "trades.csv", parse_dates=["entry_time"])
    mine["time"] = mine["entry_time"].dt.tz_localize(None).dt.normalize()
    print(f"Ingressi TradingView: {len(tv)} | Ingressi Python: {len(mine)}")
    tv["time"] = tv["time"].dt.tz_localize(None) if tv["time"].dt.tz is not None else tv["time"]

    matched = 0
    shifts = []
    rows = []
    used = set()
    for _, t in tv.iterrows():
        cand = mine[(mine["side"] == t["side"]) & (~mine.index.isin(used))]
        cand = cand.assign(d=(cand["time"] - t["time"]).abs()).sort_values("d")
        if not cand.empty and cand.iloc[0]["d"] <= pd.Timedelta(days=1):
            m = cand.iloc[0]
            used.add(cand.index[0])
            matched += 1
            shifts.append((m["time"] - t["time"]).days)
            rows.append((t["time"].date(), t["side"], t["price"], m["entry_price"], "ok"))
        else:
            rows.append((t["time"].date(), t["side"], t["price"], float("nan"), "MANCA in Python"))
    extra = mine[~mine.index.isin(used)]
    print(f"Ingressi coincidenti (stesso lato, +-1 giorno): {matched}/{len(tv)}")
    if shifts:
        print("Scarto in giorni (Python - TV):", pd.Series(shifts).value_counts().to_dict())
    print("\nIngressi TV senza corrispondenza in Python:")
    for r in rows:
        if r[4] != "ok":
            print("  ", r[0], r[1], f"prezzo TV {r[2]}")
    print("\nIngressi Python che TV non ha:")
    for _, m in extra.iterrows():
        print("  ", m["time"].date(), m["side"], f"prezzo {m['entry_price']:.2f}")


if __name__ == "__main__":
    main()

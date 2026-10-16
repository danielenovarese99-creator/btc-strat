"""Download/lettura candele giornaliere BTC (solo barre CHIUSE)."""

from datetime import datetime, timezone

import pandas as pd

import config as cfg


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    if "volume" not in df:
        df["volume"] = 0.0
    return df[["time", "open", "high", "low", "close", "volume"]]


def load_csv(path: str) -> pd.DataFrame:
    """
    CSV con colonne time,open,high,low,close[,volume]. 'time' puo' essere unix (secondi o ms)
    oppure una data ISO. L'export "Export chart data" di TradingView va bene cosi' com'e'.
    Se la serie include la barra odierna ancora in formazione, va esclusa a mano.
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    t = df["time"]
    if pd.api.types.is_numeric_dtype(t):
        unit = "ms" if t.iloc[0] > 1e11 else "s"
        df["time"] = pd.to_datetime(t, unit=unit, utc=True)
    else:
        df["time"] = pd.to_datetime(t, utc=True)
    df["time"] = df["time"].dt.normalize()
    return _clean(df)


def fetch_hyperliquid(coin: str = None) -> pd.DataFrame:
    """Candele 1d da Hyperliquid, scartando la barra in corso (la nuova giornata appena iniziata)."""
    from hyperliquid.info import Info
    from hyperliquid.utils import constants

    coin = coin or cfg.COIN
    base_url = constants.TESTNET_API_URL if cfg.USE_TESTNET else constants.MAINNET_API_URL
    info = Info(base_url, skip_ws=True)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int(datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    raw = info.candles_snapshot(coin, cfg.CANDLE_INTERVAL, start_ms, now_ms)
    if not raw:
        raise RuntimeError(f"Nessuna candela ricevuta per {coin}")
    df = pd.DataFrame(raw).rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    closed = df["T"].astype("int64") < now_ms        # T = istante di chiusura della candela
    df = df[closed].copy()
    df["time"] = pd.to_datetime(df["t"].astype("int64"), unit="ms", utc=True)
    return _clean(df)

"""
Run giornaliero della strategia 1349_BTC (da lanciare alle 00:01-00:03 UTC con cron).
1) scarica le candele giornaliere CHIUSE di BTC  2) calcola segnali e stato della strategia
3) porta la posizione su Hyperliquid al target (long/short).
"""

import sys
from datetime import datetime, timedelta, timezone

import config as cfg
import data as data_mod
import strategy as strat


def main() -> int:
    now = datetime.now(timezone.utc)
    print(f"\n===== 1349_BTC {now:%Y-%m-%d %H:%M:%S} UTC | DRY_RUN={cfg.DRY_RUN} | "
          f"{'TESTNET' if cfg.USE_TESTNET else 'MAINNET'} =====")

    df = data_mod.fetch_hyperliquid()
    last = df["time"].iloc[-1]
    expected = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    print(f"Ultima barra chiusa: {last:%Y-%m-%d} close={df['close'].iloc[-1]:.2f} ({len(df)} barre)")
    if last < expected:
        print(f"[ERRORE] dati non aggiornati: ultima barra {last:%Y-%m-%d}, attesa {expected:%Y-%m-%d}. Esco senza operare.")
        return 1

    sig = strat.compute_signals(df)
    pos = strat.run_state_machine(sig, cfg.STRATEGY_START)
    target, prev = int(pos.iloc[-1]), int(pos.iloc[-2])
    flip_today = target != prev
    r = sig.iloc[-1]
    print(f"Oscillatore={r['oscillator']:.3f} signal={r['signal']:.3f} | long_cond={bool(r['long_cond'])} "
          f"short_cond={bool(r['short_cond'])} | posizione strategia: ieri {prev:+d} -> oggi {target:+d}"
          f"{'  (FLIP OGGI)' if flip_today else ''}")

    if not cfg.DRY_RUN and (not cfg.ACCOUNT_ADDRESS or not cfg.AGENT_PRIVATE_KEY):
        print("[ERRORE] credenziali mancanti in .env")
        return 1

    from executor import get_exchange, get_info, move_to_target
    info = get_info()
    exchange = get_exchange() if not cfg.DRY_RUN else None
    ok = move_to_target(info, exchange, cfg.COIN, target, flip_today)
    print("Run completata.\n" if ok else "Run terminata CON ERRORI.\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

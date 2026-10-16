"""
Configurazione della strategia "1349_BTC" (porting da TradingView, Pine v6).

I parametri della strategia sono quelli dei settings che hai fornito; i valori letti
da .env (capitale, dry-run, ecc.) si cambiano senza toccare il codice.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Parametri strategia (settings TradingView)
# ---------------------------------------------------------------------------
# ROC / oscillatore
ROC_LEN = 20
MA_LEN = 25
SIG_LEN = 57
CALC_SOURCE = "hlc3"          # (H+L+C)/3 come nei tuoi settings; il default dello script Pine era hlcc4
NEUTRAL_THRESHOLD = 0.5       # presente nello script ma NON usato nelle condizioni di ingresso
MA_TYPE = "TEMA"              # nello script e' selezionabile, qui implementato solo TEMA

# EMD trend ("Enhanced" deviation trend)
EMD_AVG_TYPE = "DEMA"
EMD_LENGTH = 62
EMD_MULT = 1.75

# LSMA filter
LSMA_LEN = 10
LSMA_OFFSET = 0

# ALMA supertrend
ST_FACTOR = 1.6
ST_SD_LEN = 30
ALMA_LEN = 16
ALMA_SIGMA = 3.0
ALMA_OFFSET = 0.95

# Mediana (condizione di short: crossunder del prezzo sotto la mediana)
MEDIAN_LEN = 54

# NON usati dalle condizioni di ingresso dello script (calcolati ma senza effetto sui trade):
#   Hull filter (len 29), Keltner/ATR (atr 0.3, period 17), trendUP/DOWN, longMomentumSignal.
# Per questo non sono implementati.

# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------
STRATEGY_START = "2023-01-01"   # backtestStartDate: i trade partono da questa data (UTC)
COIN = "BTC"
CANDLE_INTERVAL = "1d"

# ---------------------------------------------------------------------------
# Live (letti da .env)
# ---------------------------------------------------------------------------
ACCOUNT_ADDRESS = os.environ.get("HL_ACCOUNT_ADDRESS", "")
AGENT_PRIVATE_KEY = os.environ.get("HL_AGENT_PRIVATE_KEY", "")
USE_TESTNET = os.environ.get("HL_ENV", "mainnet").lower() == "testnet"

# Se valorizzato, ordini e posizioni sono quelli di quel sub-account (consigliato: vedi README).
VAULT_ADDRESS = os.environ.get("HL_VAULT_ADDRESS", "").strip() or None

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# Capitale assegnato alla strategia in USD (obbligatorio per operare) e moltiplicatore:
# notional target = STRAT_CAPITAL_USD * LEVERAGE_FACTOR. TradingView usa 100% equity senza leva => 1.0
STRAT_CAPITAL_USD = float(os.environ.get("STRAT_CAPITAL_USD", "0") or 0)
LEVERAGE_FACTOR = float(os.environ.get("LEVERAGE_FACTOR", "1.0"))

# Se true, quando sei flat su Hyperliquid NON entri subito nello stato corrente della
# strategia: aspetti il prossimo flip (cambio di posizione) generato dalla strategia.
WAIT_FOR_FLIP = os.environ.get("WAIT_FOR_FLIP", "false").lower() == "true"

MIN_NOTIONAL_USD = 10.0
IOC_SLIPPAGE_BUFFER = 0.005     # 0.5% di buffer sul limit price degli ordini IOC

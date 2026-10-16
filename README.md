# 1349_BTC - strategia TradingView portata su Hyperliquid

Strategia long & short su BTC (timeframe 1D), stop-and-reverse: sei sempre dentro (long o short) dopo il primo segnale,
100% del capitale assegnato, nessuno stop. Porting fedele dello script Pine v6 `1349_BTC`.

## Cosa e' implementato (e cosa no)
Condizioni di ingresso dello script, valutate alla chiusura della barra:
- **LONG**  = oscillatore > 0  E  supertrend-ALMA rialzista  E  (EMD trend rialzista  O  LSMA in salita)
- **SHORT** = oscillatore < signal  E  crossunder(close, mediana 54)  E  (EMD trend ribassista  O  LSMA in discesa)

Implementati con i tuoi settings: ROC 20 / MA 25 (TEMA) / signal 57 / sorgente hlc3, EMD (DEMA 62, mult 1.75),
LSMA 10, supertrend (factor 1.6, SD 30, ALMA 16/sigma 3/offset 0.95), mediana 54.

**Calcolati nello script ma senza effetto sui trade** (quindi non portati): Hull filter (29), Keltner/ATR
(atr 0.3, period 17), trendUP/DOWN, longMomentumSignal, neutral threshold 0.5. Il campo "atr period 0" non conta.

Particolarita' dello Pine replicate di proposito: nel supertrend la deviazione standard e' calcolata sulla sorgente
del ROC (hlc3) mentre l'ALMA e' sul close, perche' `st()` viene chiamata con `src`.

## Assunzioni da confermare
1. Timeframe giornaliero (1D) su BTC, barre che chiudono alle 00:00 UTC.
2. Sorgente di calcolo hlc3 = (H+L+C)/3, come scritto nei tuoi settings.
3. Data di inizio 1/1/2023 (`STRATEGY_START` in config.py); i dati precedenti servono solo da warm-up degli indicatori.

## 1. Verificare i +724% (backtest)
I prezzi di TradingView (exchange/simbolo del tuo grafico) possono differire da quelli di Hyperliquid, quindi per un
confronto esatto usa gli stessi dati del tuo grafico:
```bash
# TradingView: sul grafico BTC 1D -> menu del grafico -> "Esporta dati del grafico" (CSV con time,open,high,low,close)
python backtest.py --csv btc_daily.csv                 # stessa data di inizio, senza commissioni (come TV)
python backtest.py                                     # stesso test con le candele di Hyperliquid
python backtest.py --fee 0.00045                       # con commissioni taker per lato
```
Per confrontare trade per trade con TradingView: Strategy Tester -> Lista dei trade -> esporta, poi
```bash
python compare_tv_trades.py tv_trades.csv trades.csv
```
Serve almeno 1 anno di storico prima del 2023: il supertrend e l'EMD hanno memoria.

## 2. Esecuzione giornaliera
Alle 00:01-00:03 UTC la candela giornaliera e' chiusa: `main.py` scarica le barre chiuse, ricostruisce lo stato della
strategia dal 1/1/2023 e porta la posizione BTC al target. Un flip long<->short e' un solo ordine IOC (chiude e riapre).
Se la direzione e' gia' giusta non fa nulla (la size si fissa all'ingresso, come su TradingView).
`WAIT_FOR_FLIP=true` evita di entrare subito nello stato corrente al primo avvio.

## 3. Attenzione: conflitto con il sistema RAPS
Su Hyperliquid c'e' UNA sola posizione BTC per account. Il sistema RAPS chiude ogni posizione che non e' nel suo
target, quindi sullo STESSO account chiuderebbe il long/short di questa strategia (e viceversa).
Soluzione consigliata: un **sub-account** dedicato (app Hyperliquid -> Sub-accounts), finanziato con il capitale della
strategia, e `HL_VAULT_ADDRESS=<indirizzo del sub-account>` in .env. Verificalo in dry-run e poi con un ordine di prova.

## 4. Installazione (nuova cartella o repo)
```bash
mkdir -p /root/btc_1349 && cd /root/btc_1349        # oppure: git clone <tuo-repo> /root/btc_1349
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && chmod 600 .env && nano .env  # DRY_RUN=true all'inizio
python main.py                                       # test in dry-run
```
Cron (sfalsato di 2 minuti rispetto a RAPS):
```
2 0 * * * cd /root/btc_1349 && /root/btc_1349/venv/bin/python main.py >> /root/btc_1349/run.log 2>&1
```

## Rischi da tenere presente
- Sempre sul mercato, 100% del capitale assegnato, nessuno stop: i drawdown possono essere profondi (guarda il max
  drawdown del backtest, e considera che TradingView lo misura sulle barre).
- Il backtest senza commissioni, slippage e funding e' ottimistico; i parametri sono ottimizzati sullo storico
  (attenzione all'overfitting).
- Parti in dry-run e con un capitale piccolo.

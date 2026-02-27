# Setup

## 1) Install dependencies

```bash
cd /Users/jarvis/workspace/labs/trading-agent-league
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Run CLI backtest (sample command)

```bash
python3 -m engine.market_replay \
  --csv data/sample_ohlcv.csv \
  --initial-capital 10000 \
  --strategies buy_hold sma_crossover rsi_mean_reversion \
  --output-dir results
```

## 3) Run Streamlit dashboard

```bash
streamlit run app/dashboard.py
```

## CSV format

The backtester expects:

`timestamp,open,high,low,close,volume`

Use `data/sample_ohlcv.csv` as the reference schema.

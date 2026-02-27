# Trading Agent League (Simulation)

## Goal
Build a fully virtual stock/BTC simulation where multiple AI agents trade under fixed rules, then rank them by risk-adjusted performance.

## Scope (MVP)
- Replay historical OHLCV data (stocks + BTC)
- 3 agents with different strategies
- Order engine with fee/slippage
- Risk guardrails (max daily loss, max drawdown)
- Scoreboard (Return, MDD, Sharpe, Win Rate)
- Simple web dashboard

## Folders
- `engine/` market replay + order execution + risk controls
- `app/` dashboard/API
- `data/` source datasets and loaders
- `results/` run outputs and leaderboard snapshots
- `docs/` specs and evaluation rules

## Next
1. Finalize MVP spec and evaluation metrics
2. Implement simulation engine
3. Add dashboard + run manager
4. Run league and rank agents

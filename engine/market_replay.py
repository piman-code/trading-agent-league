from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

from engine.agents import BaseAgent, get_baseline_agents
from engine.order_engine import OrderEngine
from engine.risk import RiskConfig, RiskManager


REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


@dataclass
class BacktestResult:
    strategy: str
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: Dict[str, float]


@dataclass
class LeagueResult:
    leaderboard: pd.DataFrame
    backtests: Dict[str, BacktestResult]


def load_ohlcv_csv(csv_path: str | Path) -> pd.DataFrame:
    data = pd.read_csv(csv_path)
    missing = [col for col in REQUIRED_COLUMNS if col not in data.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    frame = data[REQUIRED_COLUMNS].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    if frame["timestamp"].isna().any():
        raise ValueError("timestamp column contains invalid values")

    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
        if frame[col].isna().any():
            raise ValueError(f"column '{col}' contains invalid numeric values")

    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


def compute_metrics(equity_curve: pd.DataFrame, trades: pd.DataFrame, initial_capital: float) -> Dict[str, float]:
    if equity_curve.empty:
        return {
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "win_rate": 0.0,
        }

    equity = equity_curve["equity"].astype(float)
    final_equity = float(equity.iloc[-1])
    total_return = (final_equity / initial_capital) - 1.0

    rolling_peak = equity.cummax()
    drawdown = (equity / rolling_peak) - 1.0
    max_drawdown = abs(float(drawdown.min()))

    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or np.isclose(returns.std(ddof=0), 0.0):
        sharpe = 0.0
    else:
        sharpe = float(np.sqrt(252) * returns.mean() / returns.std(ddof=0))

    closed_trades = trades[trades["side"] == "sell"] if not trades.empty else pd.DataFrame()
    if closed_trades.empty:
        win_rate = 0.0
    else:
        win_rate = float((closed_trades["realized_pnl"] > 0).mean())

    return {
        "total_return": float(total_return),
        "max_drawdown": float(max_drawdown),
        "sharpe": float(sharpe),
        "win_rate": float(win_rate),
    }


def run_backtest(
    data: pd.DataFrame,
    agent: BaseAgent,
    initial_capital: float,
    slippage_bps: float = 2.0,
    fee_bps: float = 5.0,
    risk_config: RiskConfig | None = None,
) -> BacktestResult:
    order_engine = OrderEngine(
        initial_capital=initial_capital,
        slippage_bps=slippage_bps,
        fee_bps=fee_bps,
    )
    risk_manager = RiskManager(risk_config)

    agent.reset()
    agent.prepare(data)

    for i, row in data.iterrows():
        timestamp = pd.Timestamp(row["timestamp"])
        close_price = float(row["close"])
        equity_before = order_engine.total_equity(close_price)
        risk_manager.register_equity(timestamp, equity_before)

        signal = agent.on_bar(i, row, order_engine.position_qty)
        action = signal.action.lower()

        if action == "buy" and risk_manager.can_add_risk():
            qty = risk_manager.size_buy_qty(
                requested_fraction=signal.size,
                price=close_price,
                cash=order_engine.cash,
                equity=equity_before,
                current_position_qty=order_engine.position_qty,
            )
            order_engine.execute_order(timestamp, "buy", qty, close_price)
        elif action == "sell":
            qty = risk_manager.size_sell_qty(
                requested_fraction=signal.size,
                current_position_qty=order_engine.position_qty,
            )
            order_engine.execute_order(timestamp, "sell", qty, close_price)

        order_engine.mark_to_market(timestamp, close_price)

    trades = order_engine.trades_frame()
    equity_curve = order_engine.equity_frame()
    metrics = compute_metrics(equity_curve, trades, initial_capital)

    return BacktestResult(
        strategy=agent.name,
        trades=trades,
        equity_curve=equity_curve,
        metrics=metrics,
    )


def run_league(
    csv_path: str | Path,
    strategies: Iterable[str] | None = None,
    initial_capital: float = 10_000.0,
    slippage_bps: float = 2.0,
    fee_bps: float = 5.0,
    risk_config: RiskConfig | None = None,
) -> LeagueResult:
    data = load_ohlcv_csv(csv_path)
    available = get_baseline_agents()

    selected = list(strategies) if strategies else list(available.keys())
    unknown = [name for name in selected if name not in available]
    if unknown:
        raise ValueError(f"Unknown strategy name(s): {unknown}. Available: {list(available.keys())}")

    backtests: Dict[str, BacktestResult] = {}
    leaderboard_rows: List[Dict[str, float | str]] = []

    for strategy in selected:
        result = run_backtest(
            data=data,
            agent=available[strategy],
            initial_capital=initial_capital,
            slippage_bps=slippage_bps,
            fee_bps=fee_bps,
            risk_config=risk_config,
        )
        backtests[strategy] = result

        final_equity = float(result.equity_curve["equity"].iloc[-1]) if not result.equity_curve.empty else initial_capital
        leaderboard_rows.append(
            {
                "strategy": strategy,
                "final_equity": final_equity,
                "total_return": result.metrics["total_return"],
                "max_drawdown": result.metrics["max_drawdown"],
                "sharpe": result.metrics["sharpe"],
                "win_rate": result.metrics["win_rate"],
            }
        )

    leaderboard = pd.DataFrame(leaderboard_rows).sort_values("total_return", ascending=False).reset_index(drop=True)
    return LeagueResult(leaderboard=leaderboard, backtests=backtests)


def save_league_results(result: LeagueResult, output_dir: str | Path, run_tag: str | None = None) -> Dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    run_id = run_tag or datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
    artifact_paths: Dict[str, str] = {}

    leaderboard_path = output_path / f"{run_id}_leaderboard.csv"
    result.leaderboard.to_csv(leaderboard_path, index=False)
    artifact_paths["leaderboard"] = str(leaderboard_path)

    for strategy, backtest in result.backtests.items():
        safe_name = strategy.replace(" ", "_")
        trades_path = output_path / f"{run_id}_{safe_name}_trades.csv"
        equity_path = output_path / f"{run_id}_{safe_name}_equity.csv"
        backtest.trades.to_csv(trades_path, index=False)
        backtest.equity_curve.to_csv(equity_path, index=False)
        artifact_paths[f"{strategy}_trades"] = str(trades_path)
        artifact_paths[f"{strategy}_equity"] = str(equity_path)

    return artifact_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading Agent League market replay CLI")
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV file")
    parser.add_argument("--initial-capital", type=float, default=10_000.0, help="Initial capital")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["buy_hold", "sma_crossover", "rsi_mean_reversion"],
        help="Strategy names to run",
    )
    parser.add_argument("--slippage-bps", type=float, default=2.0, help="Execution slippage in bps")
    parser.add_argument("--fee-bps", type=float, default=5.0, help="Fee in bps")
    parser.add_argument("--max-position-pct", type=float, default=1.0, help="Maximum position as pct of equity")
    parser.add_argument("--max-daily-drawdown-pct", type=float, default=0.05, help="Daily drawdown cutoff")
    parser.add_argument("--output-dir", default="results", help="Directory for result artifacts")
    parser.add_argument("--run-tag", default=None, help="Optional run tag for output filenames")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    risk_config = RiskConfig(
        max_position_pct=args.max_position_pct,
        max_daily_drawdown_pct=args.max_daily_drawdown_pct,
    )
    league = run_league(
        csv_path=args.csv,
        strategies=args.strategies,
        initial_capital=args.initial_capital,
        slippage_bps=args.slippage_bps,
        fee_bps=args.fee_bps,
        risk_config=risk_config,
    )
    artifacts = save_league_results(league, output_dir=args.output_dir, run_tag=args.run_tag)

    print("Leaderboard:")
    print(league.leaderboard.to_string(index=False))
    print("\nSaved artifacts:")
    for key, path in artifacts.items():
        print(f"- {key}: {path}")


if __name__ == "__main__":
    main()


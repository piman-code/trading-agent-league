from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from engine.agents import get_baseline_agents
from engine.market_replay import run_league
from engine.risk import RiskConfig


def _format_leaderboard(leaderboard: pd.DataFrame) -> pd.DataFrame:
    view = leaderboard.copy()
    for col in ["total_return", "max_drawdown", "win_rate"]:
        view[col] = (view[col] * 100.0).round(2)
    view["sharpe"] = view["sharpe"].round(3)
    view["final_equity"] = view["final_equity"].round(2)
    view = view.rename(
        columns={
            "total_return": "total_return_%",
            "max_drawdown": "max_drawdown_%",
            "win_rate": "win_rate_%",
        }
    )
    return view


def main() -> None:
    st.set_page_config(page_title="Trading Agent League", layout="wide")
    st.title("Trading Agent League - MVP")
    st.caption("CSV OHLCV backtesting with baseline agent strategies")

    default_csv = str((ROOT_DIR / "data" / "sample_ohlcv.csv").resolve())
    all_strategies = list(get_baseline_agents().keys())

    with st.sidebar:
        st.header("Run Settings")
        csv_path = st.text_input("CSV path", value=default_csv)
        initial_capital = st.number_input("Initial capital", min_value=1.0, value=10_000.0, step=1_000.0)
        selected = st.multiselect("Strategies", all_strategies, default=all_strategies)
        slippage_bps = st.number_input("Slippage (bps)", min_value=0.0, value=2.0, step=1.0)
        fee_bps = st.number_input("Fee (bps)", min_value=0.0, value=5.0, step=1.0)
        max_position_pct = st.slider("Max position (% of equity)", min_value=0.1, max_value=1.0, value=1.0, step=0.1)
        max_daily_dd_pct = st.slider("Daily max drawdown (%)", min_value=1.0, max_value=20.0, value=5.0, step=1.0)
        run_btn = st.button("Run Backtest", type="primary")

    if not run_btn:
        st.info("Configure settings in the sidebar, then click 'Run Backtest'.")
        return

    if not selected:
        st.error("Pick at least one strategy.")
        return

    try:
        risk_config = RiskConfig(
            max_position_pct=float(max_position_pct),
            max_daily_drawdown_pct=float(max_daily_dd_pct / 100.0),
        )
        league = run_league(
            csv_path=csv_path,
            strategies=selected,
            initial_capital=float(initial_capital),
            slippage_bps=float(slippage_bps),
            fee_bps=float(fee_bps),
            risk_config=risk_config,
        )
    except Exception as exc:
        st.error(f"Backtest failed: {exc}")
        return

    st.subheader("Leaderboard")
    st.dataframe(_format_leaderboard(league.leaderboard), use_container_width=True)

    st.subheader("Equity Curves")
    chart_frames = []
    for strategy, result in league.backtests.items():
        frame = result.equity_curve[["timestamp", "equity"]].copy()
        frame["strategy"] = strategy
        chart_frames.append(frame)

    if chart_frames:
        chart_data = pd.concat(chart_frames, ignore_index=True)
        pivot = chart_data.pivot(index="timestamp", columns="strategy", values="equity")
        st.line_chart(pivot, use_container_width=True)
    else:
        st.warning("No equity data to plot.")


if __name__ == "__main__":
    main()


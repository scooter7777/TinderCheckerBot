#!/usr/bin/env python3
"""
ETH/USDT 交易策略回测框架
===========================
使用方法:
  python3 backtest.py                     # 默认 SMA 策略, 120 天 Binance 数据
  python3 backtest.py --strategy rsi      # RSI 策略
  python3 backtest.py --strategy macd     # MACD 策略
  python3 backtest.py --days 365          # 拉取 1 年数据
  python3 backtest.py --csv data.csv       # 从 CSV 加载（必须含 timestamp,open,high,low,close,volume）
  python3 backtest.py --help              # 完整参数

依赖:
  pip install pandas numpy matplotlib ccxt
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 解析参数
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="ETH/USDT 交易策略回测")
    p.add_argument("--strategy", choices=["sma", "rsi", "macd"], default="sma",
                   help="策略: sma (金叉死叉), rsi (超买超卖), macd (金叉死叉)")
    p.add_argument("--timeframe", default="1h",
                   help="K线周期: 1m,5m,15m,30m,1h,4h,1d (默认 1h)")
    p.add_argument("--days", type=int, default=120,
                   help="从 Binance 拉取多少天的 K 线 (默认 120)")
    p.add_argument("--csv", help="从 CSV 文件加载数据, 跳过网络请求", default=None)
    p.add_argument("--commission", type=float, default=0.001,
                   help="单边手续费率, 默认 0.001 (千分之一)")
    p.add_argument("--sma-fast", type=int, default=7,
                   help="SMA 快线周期 (默认 7)")
    p.add_argument("--sma-slow", type=int, default=25,
                   help="SMA 慢线周期 (默认 25)")
    p.add_argument("--rsi-period", type=int, default=14,
                   help="RSI 周期 (默认 14)")
    p.add_argument("--rsi-overbought", type=float, default=70,
                   help="RSI 超买阈值 (默认 70)")
    p.add_argument("--rsi-oversold", type=float, default=30,
                   help="RSI 超卖阈值 (默认 30)")
    p.add_argument("--macd-fast", type=int, default=12,
                   help="MACD 快线周期 (默认 12)")
    p.add_argument("--macd-slow", type=int, default=26,
                   help="MACD 慢线周期 (默认 26)")
    p.add_argument("--macd-signal", type=int, default=9,
                   help="MACD 信号线周期 (默认 9)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    """一笔已平仓的交易"""
    entry_idx: int
    exit_idx: int
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    pnl_pct: float
    reason: str = ""


@dataclass
class Portfolio:
    """记录每个时间点的账户状态"""
    equity: list
    in_position: bool
    position_side: str
    entry_price: float
    entry_idx: int


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

def fetch_data(days: int, timeframe: str = "1h") -> pd.DataFrame:
    """通过 CCXT 从 Binance 拉取 ETH/USDT K 线"""
    import ccxt

    exchange = ccxt.binance({"options": {"defaultType": "spot"}})
    since = exchange.parse8601(
        (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    )
    print(f"  ↓ 正在从 Binance 拉取 ETH/USDT 近 {days} 天的 1h 数据…")
    ohlcv = exchange.fetch_ohlcv("ETH/USDT", timeframe=timeframe, since=since, limit=None)
    print(f"  ✓ 获取到 {len(ohlcv)} 根 K 线")

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def load_csv(path: str) -> pd.DataFrame:
    """从 CSV 加载数据"""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    if "timestamp" in df.columns:
        df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    df.columns = [c.lower() for c in df.columns]
    print(f"  ✓ 从 {path} 加载 {len(df)} 行数据")
    return df


# ---------------------------------------------------------------------------
# 策略信号
# ---------------------------------------------------------------------------

def add_sma_signals(df: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    """SMA 金叉 → 买入, 死叉 → 卖出"""
    df["sma_fast"] = df["close"].rolling(fast).mean()
    df["sma_slow"] = df["close"].rolling(slow).mean()
    df["signal"] = 0
    df.loc[df["sma_fast"] > df["sma_slow"], "signal"] = 1
    df["signal"] = df["signal"].diff()
    return df


def add_rsi_signals(df: pd.DataFrame, period: int, ob: float, os: float) -> pd.DataFrame:
    """RSI 上穿超卖 → 买入, 下穿超买 → 卖出"""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["signal"] = 0
    df.loc[df["rsi"] < os, "signal"] = 1
    df.loc[df["rsi"] > ob, "signal"] = -1
    df["prev_signal"] = df["signal"].shift(1).fillna(0)
    buy = (df["signal"] == 1) & (df["prev_signal"] != 1)
    sell = (df["signal"] == -1) & (df["prev_signal"] != -1)
    df["entry"] = 0
    df["exit"] = 0
    df.loc[buy, "entry"] = 1
    df.loc[sell, "exit"] = 1
    return df


def add_macd_signals(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    """MACD 金叉 → 买入, 死叉 → 卖出"""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["signal"] = 0
    df.loc[df["macd"] > df["macd_signal"], "signal"] = 1
    df["signal"] = df["signal"].diff()
    return df


def add_volatility_regime(df: pd.DataFrame, atr_period: int = 20) -> pd.DataFrame:
    """基于 ATR 百分位将每根 K 线标注为 低/正常/高 波动率"""
    df["tr"] = pd.concat([
        (df["high"] - df["low"]).abs(),
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = df["tr"].rolling(atr_period).mean()
    df["atr_pct"] = df["atr"] / df["close"] * 100
    df["regime"] = "normal"
    pct = df["atr_pct"].rank(pct=True)
    df.loc[(pct < 0.25) & (pct.notna()), "regime"] = "low"
    df.loc[(pct >= 0.75) & (pct.notna()), "regime"] = "high"
    return df


# ---------------------------------------------------------------------------
# 回测引擎
# ---------------------------------------------------------------------------


def run_backtest(
    df: pd.DataFrame, strategy: str, commission: float, args,
) -> tuple[pd.DataFrame, list[Trade], Portfolio]:
    """执行回测

    在 Trade 上记录 trade_regime (开仓时市况).
    在 portfolio.equity 基础上额外把 regimes 也记下来用于按市况分析。
    我们在开仓时判断当前 K 线的 regime, 记入 Trade.
    """

    # 确保有 regime 列
    if "regime" not in df.columns:
        df["regime"] = "normal"

    portfolio = Portfolio(
        equity=[], in_position=False, position_side="",
        entry_price=0.0, entry_idx=0,
    )
    trades: list[Trade] = []

    if strategy == "rsi":
        buy_col = "entry"
        sell_col = "exit"
    else:
        buy_col = "signal"
        sell_col = "signal"

    for idx in range(len(df)):
        row = df.iloc[idx]
        price = float(row["close"])

        if idx == 0:
            portfolio.equity.append(100_000.0)
            continue

        prev_equity = portfolio.equity[-1]

        # 开仓
        if not portfolio.in_position:
            is_buy = (buy_col == "signal" and row.get("signal", 0) == 1) or \
                     (buy_col == "entry" and row.get("entry", 0) == 1)
            if is_buy:
                portfolio.in_position = True
                portfolio.position_side = "long"
                portfolio.entry_price = price
                portfolio.entry_idx = idx
                entry_regime = row.get("regime", "normal")
                portfolio.equity.append(prev_equity)
                continue
            portfolio.equity.append(prev_equity)
            continue

        # 持仓中: 检查平仓
        should_exit = (sell_col == "signal" and row.get("signal", 0) == -1) or \
                      (sell_col == "exit" and row.get("exit", 0) == 1)

        if should_exit:
            raw_return = (price / portfolio.entry_price) - 1.0
            net_return = raw_return - commission * 2
            new_equity = prev_equity * (1 + net_return)

            trades.append(Trade(
                entry_idx=portfolio.entry_idx,
                exit_idx=idx,
                entry_time=str(df.iloc[portfolio.entry_idx].name),
                exit_time=str(row.name),
                side="long",
                entry_price=portfolio.entry_price,
                exit_price=price,
                pnl_pct=net_return * 100,
                reason="信号",
            ))
            trades[-1].regime = entry_regime
            portfolio.in_position = False
            portfolio.equity.append(new_equity)
            continue

        portfolio.equity.append(prev_equity)

    # 强制平仓
    if portfolio.in_position:
        last = df.iloc[-1]
        price = float(last["close"])
        raw_return = (price / portfolio.entry_price) - 1.0
        net_return = raw_return - commission * 2
        new_equity = portfolio.equity[-1] * (1 + net_return)

        trades.append(Trade(
            entry_idx=portfolio.entry_idx,
            exit_idx=len(df) - 1,
            entry_time=str(df.iloc[portfolio.entry_idx].name),
            exit_time=str(last.name),
            side="long",
            entry_price=portfolio.entry_price,
            exit_price=price,
            pnl_pct=net_return * 100,
            reason="强平(期末)",
        ))
        trades[-1].regime = entry_regime
        portfolio.in_position = False
        portfolio.equity[-1] = new_equity

    # 持仓标记
    df["in_position"] = False
    for t in trades:
        df.loc[df.index[t.entry_idx] : df.index[t.exit_idx], "in_position"] = True
        # 顺便把 regime 刷到 trade 对象上面 (已在上面赋值)

    return df, trades, portfolio


# ---------------------------------------------------------------------------
# 绩效指标
# ---------------------------------------------------------------------------

def calc_metrics(equity: list[float], trades: list[Trade], risk_free_rate: float = 0.02):
    """计算核心绩效指标"""
    eq = np.array(equity)
    init = eq[0]
    final = eq[-1]
    total_return_pct = (final / init - 1) * 100

    hourly_returns = np.diff(eq) / eq[:-1]
    n_hours = len(hourly_returns)
    n_years = n_hours / (365.25 * 24)

    ann_return = (final / init) ** (1 / n_years) - 1 if n_years > 0 else 0
    ann_return_pct = ann_return * 100

    if len(hourly_returns) > 0 and np.std(hourly_returns) > 0:
        excess_hourly = hourly_returns - risk_free_rate / (365.25 * 24)
        sharpe = np.mean(excess_hourly) / np.std(hourly_returns) * np.sqrt(365.25 * 24)
    else:
        sharpe = 0.0

    peak = np.maximum.accumulate(eq)
    drawdown = (eq - peak) / peak
    max_dd_pct = np.min(drawdown) * 100

    n_trades = len(trades)
    if n_trades > 0:
        wins = sum(1 for t in trades if t.pnl_pct > 0)
        losses = sum(1 for t in trades if t.pnl_pct <= 0)
        win_rate = wins / n_trades * 100
        avg_win = np.mean([t.pnl_pct for t in trades if t.pnl_pct > 0]) if wins > 0 else 0
        avg_loss = np.mean([t.pnl_pct for t in trades if t.pnl_pct <= 0]) if losses > 0 else 0
        best_trade = max(t.pnl_pct for t in trades)
        worst_trade = min(t.pnl_pct for t in trades)
        total_gain = sum(t.pnl_pct for t in trades if t.pnl_pct > 0)
        total_loss = sum(t.pnl_pct for t in trades if t.pnl_pct <= 0)
        profit_factor = abs(total_gain / total_loss) if total_loss != 0 else float("inf")
    else:
        win_rate = avg_win = avg_loss = best_trade = worst_trade = profit_factor = 0

    return {
        "初始资金": init,
        "最终净值": final,
        "总收益率 %": round(total_return_pct, 2),
        "年化收益率 %": round(ann_return_pct, 2),
        "夏普比率": round(sharpe, 2),
        "最大回撤 %": round(max_dd_pct, 2),
        "交易次数": n_trades,
        "胜率 %": round(win_rate, 2),
        "平均盈利 %": round(avg_win, 2),
        "平均亏损 %": round(avg_loss, 2),
        "盈亏比": round(abs(avg_win / avg_loss) if avg_loss != 0 else float("inf"), 2),
        "最大单笔盈利 %": round(best_trade, 2),
        "最大单笔亏损 %": round(worst_trade, 2),
        "获利因子": round(profit_factor, 2),
    }


# ---------------------------------------------------------------------------
# 可视化
# ---------------------------------------------------------------------------

def find_support_resistance(df: pd.DataFrame, window: int = 10, min_touches: int = 2) -> tuple[list, list]:
    """识别支撑位和阻力位 (基于滚动窗口的局部极值 + 价位聚类)

    返回: (支撑位列表, 阻力位列表), 每个元素为 (价格, 强度)
    """
    highs = df["high"].values
    lows = df["low"].values
    close = df["close"].values
    n = len(df)

    # 找局部高点 (阻力候选) 和局部低点 (支撑候选)
    resist_candidates = []
    support_candidates = []

    for i in range(window, n - window):
        # 局部高点: 比前后 window 根 K 都高
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, window + 1)):
            resist_candidates.append(highs[i])
        # 局部低点: 比前后 window 根 K 都低
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, window + 1)):
            support_candidates.append(lows[i])

    # 聚类: 靠得太近的合并, 保留出现次数最多的 (仅过滤一次)
    def cluster_levels(candidates, tol_pct=0.015):
        if not candidates:
            return []
        candidates = sorted(candidates)
        clusters = []      # [(avg_price, count)]
        cur_vals = [candidates[0]]
        for c in candidates[1:]:
            avg = sum(cur_vals) / len(cur_vals)
            if abs(c - avg) / avg < tol_pct:
                cur_vals.append(c)
            else:
                clusters.append((sum(cur_vals) / len(cur_vals), len(cur_vals)))
                cur_vals = [c]
        clusters.append((sum(cur_vals) / len(cur_vals), len(cur_vals)))
        # 只保留触达 >= min_touches 次的
        return [c for c in clusters if c[1] >= min_touches]

    support = cluster_levels(support_candidates)
    resistance = cluster_levels(resist_candidates)
    return support, resistance


def plot_results(df: pd.DataFrame, trades: list[Trade], equity: list[float], strategy: str):
    """三面板图表: 价格+信号 / 权益曲线 / 回撤"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    plt.rcParams["figure.dpi"] = 120
    plt.rcParams["font.size"] = 11

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True,
                                        gridspec_kw={"height_ratios": [3, 1.2, 1]})

    # 价格
    ax1.plot(df.index, df["close"], color="#1a1a2e", linewidth=0.8, label="ETH/USDT")

    if "sma_fast" in df.columns:
        ax1.plot(df.index, df["sma_fast"], color="#e94560", linewidth=0.7,
                 label=f"SMA({args.sma_fast})")
        ax1.plot(df.index, df["sma_slow"], color="#0f3460", linewidth=0.9,
                 label=f"SMA({args.sma_slow})")

    # 买卖标记
    buy_signals = df[df.get("signal", pd.Series(dtype=int)) == 1]
    sell_signals = df[df.get("signal", pd.Series(dtype=int)) == -1]
    if strategy == "rsi":
        buy_signals = df[df.get("entry", pd.Series(dtype=int)) == 1]
        sell_signals = df[df.get("exit", pd.Series(dtype=int)) == 1]

    ax1.scatter(buy_signals.index, buy_signals["close"] * 0.98,
                marker="^", color="#00c853", s=60, label="Buy", zorder=5)
    ax1.scatter(sell_signals.index, sell_signals["close"] * 1.02,
                marker="v", color="#ff1744", s=60, label="Sell", zorder=5)

    if "in_position" in df.columns:
        for i in range(len(df) - 1):
            if df["in_position"].iloc[i]:
                ax1.axvspan(df.index[i], df.index[i + 1],
                            alpha=0.08, color="#00c853")

    # 支撑 / 阻力线
    supports, resistances = find_support_resistance(df)
    for price, strength in supports:
        ax1.axhline(y=price, color="#00c853", linestyle="--", alpha=0.4, linewidth=1.2)
        ax1.text(df.index[0], price * 1.005, f"S {price:.0f}",
                 color="#00c853", fontsize=8, alpha=0.7)
    for price, strength in resistances:
        ax1.axhline(y=price, color="#ff1744", linestyle="--", alpha=0.4, linewidth=1.2)
        ax1.text(df.index[0], price * 1.005, f"R {price:.0f}",
                 color="#ff1744", fontsize=8, alpha=0.7)
    if supports or resistances:
        ax1.text(df.index[-1], df["close"].iloc[-1],
                 "  ⋮ 虚线=阻/支", fontsize=8, color="gray", alpha=0.5)

    ax1.set_ylabel("Price (USDT)")
    ax1.set_title(f"ETH/USDT Backtest — {strategy.upper()} Strategy")
    ax1.legend(loc="upper left", ncol=4, fontsize=9)
    ax1.grid(alpha=0.2)

    # 权益曲线
    eq = np.array(equity)
    ax2.plot(df.index, eq, color="#1565c0", linewidth=1.0)
    ax2.fill_between(df.index, eq[0], eq, alpha=0.08, color="#1565c0")
    ax2.axhline(y=eq[0], color="gray", linestyle="--", linewidth=0.6)
    ax2.set_ylabel("Equity (USDT)")
    ax2.set_title(f"Equity Curve — Final ${eq[-1]:,.2f}")
    ax2.grid(alpha=0.2)

    # 回撤
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak * 100
    ax3.fill_between(df.index, dd, 0, color="#e53935", alpha=0.5)
    ax3.set_ylabel("Drawdown (%)")
    ax3.set_xlabel("Time")
    ax3.grid(alpha=0.2)

    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax3.xaxis.set_major_locator(locator)
    ax3.xaxis.set_major_formatter(formatter)

    plt.tight_layout()

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_result.png")
    plt.savefig(out, bbox_inches="tight")
    print(f"\n  Chart saved: {out}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def calc_metrics_by_regime(trades: list[Trade], equity: list[float]) -> dict:
    """按市况(regime)分别计算指标"""
    result = {}
    for regime in ["low", "normal", "high"]:
        rt = [t for t in trades if t.regime == regime]
        if not rt:
            result[regime] = None
            continue
        wins = sum(1 for t in rt if t.pnl_pct > 0)
        losses = sum(1 for t in rt if t.pnl_pct <= 0)
        n = len(rt)
        win_rate = wins / n * 100 if n > 0 else 0
        avg_win = (sum(t.pnl_pct for t in rt if t.pnl_pct > 0) / wins) if wins > 0 else 0
        avg_loss = (sum(t.pnl_pct for t in rt if t.pnl_pct <= 0) / losses) if losses > 0 else 0
        result[regime] = {
            "交易次数": n,
            "胜率 %": round(win_rate, 2),
            "平均盈利 %": round(avg_win, 2),
            "平均亏损 %": round(avg_loss, 2),
            "合计收益 %": round(sum(t.pnl_pct for t in rt), 2),
        }
    return result


def main():
    global args
    args = parse_args()

    print(f"\n{'='*56}")
    print(f"  ETH/USDT 回测启动")
    print(f"  策略: {args.strategy.upper()}  |  手续费: {args.commission*100:.1f}%")
    print(f"{'='*56}\n")

    if args.csv:
        df = load_csv(args.csv)
    else:
        df = fetch_data(args.days, args.timeframe)

    if len(df) < 50:
        print("  ✗ 数据不足")
        sys.exit(1)

    print(f"  周期: {args.timeframe}  |  数据范围: {df.index[0]} → {df.index[-1]}")
    print(f"  价格区间: ${df['close'].min():.2f} ~ ${df['close'].max():.2f}\n")

    if args.strategy == "sma":
        df = add_sma_signals(df, args.sma_fast, args.sma_slow)
    elif args.strategy == "rsi":
        df = add_rsi_signals(df, args.rsi_period, args.rsi_overbought, args.rsi_oversold)
    elif args.strategy == "macd":
        df = add_macd_signals(df, args.macd_fast, args.macd_slow, args.macd_signal)

    # 波动率市况标记
    df = add_volatility_regime(df)

    df, trades, portfolio = run_backtest(df, args.strategy, args.commission, args)

    metrics = calc_metrics(portfolio.equity, trades)

    print(f"  {'─'*48}")
    print(f"  {'指标':<20} {'值':>12}")
    print(f"  {'─'*48}")
    for k, v in metrics.items():
        print(f"  {k:<20} {v:>12}")
    print(f"  {'─'*48}\n")

    # 按市况统计
    regime_stats = calc_metrics_by_regime(trades, portfolio.equity)
    print(f"  {'─'*60}")
    print(f"  {'按市况表现 (基于 ATR 波动率分档)':^56}")
    print(f"  {'─'*60}")
    print(f"  {'市况':<8} {'交易':>6} {'胜率':>8} {'平均盈利':>10} {'平均亏损':>10} {'合计收益':>10}")
    print(f"  {'─'*60}")
    for regime in ["low", "normal", "high"]:
        rs = regime_stats.get(regime)
        if rs is None:
            print(f"  {regime:<8} {'—':>6} {'—':>8} {'—':>10} {'—':>10} {'—':>10}")
            continue
        print(f"  {regime:<8} {rs['交易次数']:>6} {rs['胜率 %']:>7.1f}% "
              f"{rs['平均盈利 %']:>9.2f}% {rs['平均亏损 %']:>9.2f}% "
              f"{rs['合计收益 %']:>+8.2f}%")
    print(f"  {'─'*60}\n")

    if trades:
        print(f"  最近 5 笔交易:")
        print(f"  {'#':<3} {'时间':<22} {'方向':<6} {'入场':<10} {'出场':<10} {'盈亏%':<8} {'原因':<10}")
        print(f"  {'─'*70}")
        for i, t in enumerate(trades[-5:]):
            print(f"  {i+1:<3} {t.exit_time[:19]:<22} {t.side:<6} "
                  f"${t.entry_price:<7.2f} ${t.exit_price:<7.2f} "
                  f"{t.pnl_pct:>+6.2f}%  {t.reason:<10}")
        print()

    plot_results(df, trades, portfolio.equity, args.strategy)


if __name__ == "__main__":
    main()

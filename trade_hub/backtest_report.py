#!/usr/bin/env python3
"""生成透明的策略回测报告（真实数据、真实指标）。

用法:
  python3 backtest_report.py --data ../eth_usdt_1h_2y.csv --asset ETHUSDT
  输出 report.json + 控制台摘要
"""

import argparse, json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from backtest import (
    add_sma_signals, add_rsi_signals, add_macd_signals,
    add_volatility_regime, run_backtest, calc_metrics, calc_metrics_by_regime,
)


def load_csv(path):
    df = pd.read_csv(path, parse_dates=["ts"])
    df = df.rename(columns={"ts": "timestamp"})
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def build_strategy(df, name):
    """构造不同的策略信号，返回带 signal 列的 DataFrame。"""
    df = df.copy()
    df = add_volatility_regime(df)
    if name == "sma":
        df = add_sma_signals(df, 20, 50)
    elif name == "rsi":
        df = add_rsi_signals(df, 14, 70, 30)
    elif name == "macd":
        df = add_macd_signals(df, 12, 26, 9)
    elif name == "combo":
        df = add_sma_signals(df, 20, 50)
        df = add_rsi_signals(df, 14, 70, 30)
        df = add_macd_signals(df, 12, 26, 9)
        # 三个条件同时看多才持仓，任一转空即离场
        state = pd.Series(0, index=df.index)
        state.loc[(df["sma_fast"] > df["sma_slow"]) & (df["rsi"] > 50) & (df["macd"] > df["macd_signal"])] = 1
        state.loc[(df["sma_fast"] < df["sma_slow"]) | (df["rsi"] < 50) | (df["macd"] < df["macd_signal"])] = -1
        df["signal"] = state.diff().fillna(0)
    else:
        raise ValueError(name)
    return df


def metric_summary(metrics):
    return {
        "总收益%": metrics["总收益率 %"],
        "年化%": metrics["年化收益率 %"],
        "最大回撤%": metrics["最大回撤 %"],
        "夏普": metrics["夏普比率"],
        "胜率%": metrics["胜率 %"],
        "盈亏比": metrics["获利因子"],
        "交易次数": metrics["交易次数"],
        "平均R": metrics.get("avg_r", 0),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="../eth_usdt_1h_2y.csv")
    p.add_argument("--asset", default="ETHUSDT")
    p.add_argument("--commission", type=float, default=0.0005)
    p.add_argument("--out", default="report.json")
    args = p.parse_args()

    df = load_csv(args.data)
    if df is None or df.empty:
        print("数据加载失败")
        return 1
    start_dt = str(df.index[0])
    end_dt = str(df.index[-1])
    df = df.dropna(subset=["close"])
    df = df.reset_index()

    strategies = ["hold", "sma", "rsi", "macd", "combo"]
    results = {}
    for name in strategies:
        if name == "hold":
            # 买入并持有基准：第一根收盘买入，最后一根收盘卖出
            first = df.iloc[0]["close"]
            last = df.iloc[-1]["close"]
            hold_return = (last / first - 1) * 100
            results[name] = {
                "metrics": {
                    "总收益%": round(hold_return, 2),
                    "年化%": round(((last / first) ** (365.25 * 24 / len(df)) - 1) * 100, 2),
                    "最大回撤%": None,
                    "夏普": None,
                    "胜率%": None,
                    "盈亏比": None,
                    "交易次数": 1,
                    "平均R": None,
                },
                "regime": {},
                "trades": 1,
            }
            continue
        sdf = build_strategy(df, name)
        _, trades, portfolio = run_backtest(sdf, "sma", args.commission, args)
        metrics = calc_metrics(portfolio.equity, trades)
        by_regime = calc_metrics_by_regime(trades, portfolio.equity)
        results[name] = {
            "metrics": metric_summary(metrics),
            "regime": {
                k: ({"胜率%": v["胜率 %"], "合计收益%": v["合计收益 %"], "交易": v["交易次数"]}
                    if isinstance(v, dict) else None)
                for k, v in by_regime.items()
            },
            "trades": len(trades),
        }

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "asset": args.asset,
        "bars": len(df),
        "start": start_dt,
        "end": end_dt,
        "commission": args.commission,
        "strategies": results,
        "disclaimer": "历史回测不代表未来收益。数据来自真实历史行情，未做前视偏差处理。",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n=== 回测报告 {args.asset} ({report['bars']} 根K线) ===")
    print(f"区间: {report['start']} -> {report['end']}\n")
    for name, r in results.items():
        m = r["metrics"]
        print(f"[{name}] 收益 {m['总收益%']}% | 年化 {m['年化%']}% | 回撤 {m['最大回撤%']}% | "
              f"胜率 {m['胜率%']}% | PF {m['盈亏比']} | 夏普 {m['夏普']} | {m['交易次数']}笔")
    print(f"\n报告已保存: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

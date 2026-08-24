#!/usr/bin/env python3
"""真实合约数据 -> 机构信号。

数据源: Binance USDT-M 合约公开接口（无需密钥）。
维度:
  资金费率  - 极端正=多头拥挤(偏空), 极端负=空头拥挤(偏多)
  持仓量变化 - 上涨增仓=新多进场, 下跌增仓=新空进场, 减仓=平仓离场
  主动买卖量比 - >1 买盘占优, <1 卖盘占优
  多空账户比 - 极端=拥挤反向, 中性=顺势
  大户持仓比 - 大户方向

输出: institutional_signal.json + 控制台摘要
"""

import argparse, json, os, sys
from datetime import datetime, timezone

import requests

FAPI = "https://fapi.binance.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "institutional_signal.json")


def get(url, params):
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_futures(symbol="BTCUSDT"):
    """拉取合约数据，返回各维度。"""
    data = {}
    # 当前资金费率 + 标记价格
    pi = get(f"{FAPI}/fapi/v1/premiumIndex", {"symbol": symbol})
    data["funding_rate"] = float(pi["lastFundingRate"])
    data["mark_price"] = float(pi["markPrice"])

    # 当前持仓量
    oi = get(f"{FAPI}/fapi/v1/openInterest", {"symbol": symbol})
    data["open_interest"] = float(oi["openInterest"])

    # 历史资金费率(近24次, 8h一次)
    fr = get(f"{FAPI}/fapi/v1/fundingRate", {"symbol": symbol, "limit": 24})
    data["funding_history"] = [float(x["fundingRate"]) for x in fr]

    # 持仓量历史(1h, 近24条)
    oih = get(f"{FAPI}/futures/data/openInterestHist",
              {"symbol": symbol, "period": "1h", "limit": 24})
    data["oi_history"] = [float(x["sumOpenInterest"]) for x in oih]
    data["oi_timestamp"] = [x["timestamp"] for x in oih]

    # 主动买卖量比(1h, 近12条)
    tb = get(f"{FAPI}/futures/data/takerlongshortRatio",
             {"symbol": symbol, "period": "1h", "limit": 12})
    data["taker_history"] = [float(x["buySellRatio"]) for x in tb]

    # 全球多空账户比
    g = get(f"{FAPI}/futures/data/globalLongShortAccountRatio",
            {"symbol": symbol, "period": "1h", "limit": 12})
    data["ls_history"] = [float(x["longShortRatio"]) for x in g]

    # 大户持仓比
    t = get(f"{FAPI}/futures/data/topLongShortPositionRatio",
            {"symbol": symbol, "period": "1h", "limit": 12})
    data["top_history"] = [float(x["longShortRatio"]) for x in t]

    return data


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def score_funding(rate, history):
    """资金费率: 中性基准 0.01%。极正=-1(拥挤多), 极负=+1(拥挤空)。"""
    base = 0.0001
    if rate > base * 3:
        return -0.6, f"资金费率 {rate*100:.3f}% 偏高, 多头拥挤"
    if rate < -base * 2:
        return 0.6, f"资金费率 {rate*100:.3f}% 为负, 空头拥挤"
    return 0.0, f"资金费率 {rate*100:.3f}% 中性"


def score_oi(oi_now, oi_history, price_now):
    """持仓量变化 + 价格方向: 增仓顺势=强信号。"""
    if len(oi_history) < 8:
        return 0.0, "持仓历史不足"
    oi_prev = oi_history[-8]
    oi_chg = (oi_now - oi_prev) / oi_prev if oi_prev else 0
    # 需要价格方向: 用 taker 作为代理, 或简单用 OI 变化
    if oi_chg > 0.02:
        return 0.35, f"持仓量 {oi_chg*100:.1f}% 增仓, 资金进场"
    if oi_chg < -0.02:
        return -0.25, f"持仓量 {oi_chg*100:.1f}% 减仓, 资金离场"
    return 0.0, f"持仓量变化 {oi_chg*100:.1f}% 平稳"


def score_taker(history):
    """主动买卖量比: >1.1 买盘占优, <0.9 卖盘占优。"""
    if not history:
        return 0.0, "无主动买卖数据"
    avg = sum(history[-6:]) / len(history[-6:])
    if avg > 1.15:
        return 0.5, f"主动买/卖 {avg:.2f}, 买盘主导"
    if avg < 0.85:
        return -0.5, f"主动买/卖 {avg:.2f}, 卖盘主导"
    return 0.0, f"主动买/卖 {avg:.2f}, 均衡"


def score_ls(history, kind):
    """多空比: 2.5+ 或 0.4- 为拥挤反向; 中间顺势(轻微偏多/空)。"""
    if not history:
        return 0.0, f"{kind}数据不足"
    v = history[-1]
    if v > 2.5:
        return -0.4, f"{kind} {v:.2f}, 多头拥挤(反向)"
    if v < 0.4:
        return 0.4, f"{kind} {v:.2f}, 空头拥挤(反向)"
    if v > 1.3:
        return 0.2, f"{kind} {v:.2f}, 偏多"
    if v < 0.75:
        return -0.2, f"{kind} {v:.2f}, 偏空"
    return 0.0, f"{kind} {v:.2f}, 中性"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--out", default=OUT)
    args = p.parse_args()

    d = fetch_futures(args.symbol)
    parts = {}
    parts["funding"] = score_funding(d["funding_rate"], d["funding_history"])
    parts["oi"] = score_oi(d["open_interest"], d["oi_history"], d["mark_price"])
    parts["taker"] = score_taker(d["taker_history"])
    parts["ls"] = score_ls(d["ls_history"], "多空账户比")
    parts["top"] = score_ls(d["top_history"], "大户持仓比")

    weights = {"funding": 0.30, "oi": 0.15, "taker": 0.25, "ls": 0.15, "top": 0.15}
    total = sum(s * weights[k] for k, (s, _) in parts.items())
    total = clamp(total, -1, 1)
    direction = "bullish" if total > 0.15 else ("bearish" if total < -0.15 else "neutral")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": args.symbol,
        "mark_price": d["mark_price"],
        "funding_rate": d["funding_rate"],
        "open_interest": d["open_interest"],
        "taker_ratio": d["taker_history"][-1] if d["taker_history"] else None,
        "long_short_ratio": d["ls_history"][-1] if d["ls_history"] else None,
        "top_position_ratio": d["top_history"][-1] if d["top_history"] else None,
        "score": round(total, 3),
        "direction": direction,
        "details": {k: {"score": round(s, 2), "note": note} for k, (s, note) in parts.items()},
        "disclaimer": "基于公开合约数据的量化评分，仅反映资金结构，不构成投资建议。",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    dir_cn = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}
    print(f"\n=== {args.symbol} 机构信号 ===")
    print(f"价格: ${d['mark_price']:,.0f} | 资金费率: {d['funding_rate']*100:.3f}% | "
          f"持仓量: {d['open_interest']:,.0f} BTC")
    print(f"主动买/卖: {d['taker_history'][-1]:.2f} | 多空比: {d['ls_history'][-1]:.2f} | "
          f"大户持仓比: {d['top_history'][-1]:.2f}")
    print(f"综合评分: {total:+.2f} -> {dir_cn[direction]}")
    for k, (s, note) in parts.items():
        print(f"  {k:<8} {s:+.2f}  {note}")
    print(f"\n已保存: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

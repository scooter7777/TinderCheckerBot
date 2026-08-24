#!/usr/bin/env python3
"""透明信号账本：发布信号 -> 到期验证 -> 公开战绩。

用法:
  python3 ledger.py publish --symbol BTCUSDT --timeframe 1h --direction long \
      --entry 63000 --sl 62000 --tp 65000
  python3 ledger.py verify          # 用实时价检查未平仓信号是否触达 SL/TP
  python3 ledger.py stats           # 输出已平仓信号的真实胜率/盈亏
"""

import argparse, json, os, sys, uuid
from datetime import datetime, timezone

import requests

LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals.jsonl")


def load():
    rows = []
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return rows


def save(rows):
    with open(LEDGER, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def current_price(symbol):
    r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=15)
    r.raise_for_status()
    return float(r.json()["price"])


def cmd_publish(args):
    rows = load()
    rec = {
        "id": uuid.uuid4().hex[:8],
        "symbol": args.symbol,
        "timeframe": args.timeframe,
        "direction": args.direction,
        "entry": args.entry,
        "sl": args.sl,
        "tp": args.tp,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "status": "open",
        "outcome": None,
        "exit_price": None,
        "closed_at": None,
    }
    rows.append(rec)
    save(rows)
    print(f"信号已发布: {rec['id']} {args.direction} {args.symbol} @ {args.entry}")
    print(f"  止损 {args.sl} | 止盈 {args.tp}")
    return 0


def cmd_verify(args):
    rows = load()
    changed = 0
    for r in rows:
        if r.get("status") != "open":
            continue
        try:
            price = current_price(r["symbol"])
        except Exception as e:
            print(f"  {r['id']} 取价失败: {e}")
            continue
        if r["direction"] == "long":
            if price <= r["sl"]:
                r["status"], r["outcome"] = "closed", "loss"
                r["exit_price"] = price
            elif price >= r["tp"]:
                r["status"], r["outcome"] = "closed", "win"
                r["exit_price"] = price
        else:
            if price >= r["sl"]:
                r["status"], r["outcome"] = "closed", "loss"
                r["exit_price"] = price
            elif price <= r["tp"]:
                r["status"], r["outcome"] = "closed", "win"
                r["exit_price"] = price
        if r["status"] == "closed":
            r["closed_at"] = datetime.now(timezone.utc).isoformat()
            changed += 1
            print(f"  {r['id']} 已平仓: {r['outcome']} @ {price} (入 {r['entry']})")
    save(rows)
    print(f"本轮验证 {len(rows)} 条, 新平仓 {changed} 条")
    return 0


def cmd_stats(args):
    rows = load()
    closed = [r for r in rows if r.get("status") == "closed"]
    wins = [r for r in closed if r.get("outcome") == "win"]
    losses = [r for r in closed if r.get("outcome") == "loss"]

    rs = []
    for r in closed:
        risk = abs(r["entry"] - r["sl"])
        reward = abs(r["tp"] - r["entry"])
        if r["outcome"] == "win":
            rs.append(reward / risk if risk else 0)
        else:
            rs.append(-1.0)
    gross_win = sum(max(x, 0) for x in rs)
    gross_loss = sum(-x for x in rs if x < 0)

    stats = {
        "总信号": len(rows),
        "未平仓": len(rows) - len(closed),
        "已平仓": len(closed),
        "胜": len(wins),
        "负": len(losses),
        "胜率%": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "平均R": round(sum(rs) / len(rs), 2) if rs else 0,
        "盈利因子": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args):
    rows = load()
    print(f"{'ID':<10}{'方向':<6}{'标的':<12}{'周期':<8}{'入场':<12}{'止损':<12}{'止盈':<12}{'状态':<8}结果")
    for r in reversed(rows[-20:]):
        print(f"{r['id']:<10}{r['direction']:<6}{r['symbol']:<12}{r['timeframe']:<8}"
              f"{r['entry']:<12}{r['sl']:<12}{r['tp']:<12}{r['status']:<8}{r.get('outcome') or '-'}")
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("publish")
    pb.add_argument("--symbol", required=True)
    pb.add_argument("--timeframe", default="1h")
    pb.add_argument("--direction", choices=["long", "short"], required=True)
    pb.add_argument("--entry", type=float, required=True)
    pb.add_argument("--sl", type=float, required=True)
    pb.add_argument("--tp", type=float, required=True)
    pb.set_defaults(fn=cmd_publish)

    vb = sub.add_parser("verify")
    vb.set_defaults(fn=cmd_verify)

    sb = sub.add_parser("stats")
    sb.set_defaults(fn=cmd_stats)

    lb = sub.add_parser("list")
    lb.set_defaults(fn=cmd_list)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

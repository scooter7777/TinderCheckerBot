#!/usr/bin/env python3
"""一键刷新：机构信号 -> 信号验证 -> 战绩面板。

用法:
  python3 refresh.py                # 刷新 BTC
  python3 refresh.py --symbol ETHUSDT
"""

import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(name, args):
    print(f"\n=== {name} ===")
    r = subprocess.run([sys.executable, os.path.join(HERE, args[0])] + args[1:],
                       cwd=HERE)
    if r.returncode != 0:
        print(f"[{name}] 失败")
        sys.exit(r.returncode)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="BTCUSDT")
    args = p.parse_args()

    run("机构信号", ["futures_signals.py", "--symbol", args.symbol])
    run("信号账本验证", ["ledger.py", "verify"])
    run("生成战绩面板", ["build_dashboard.py"])
    print("\n全部完成 ✔")


if __name__ == "__main__":
    main()

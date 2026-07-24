#!/usr/bin/env python3
"""
自适应预测器
============
每 15m 预测一次 → 15m 后验证 → 调整权重 → 导出优化报告到桌面

运行:
  python3 adaptive_predictor.py --daemon   # 后台持续运行
"""
import argparse, json, os, sys, time
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd

from predict import (fetch_data, calc_indicators, signal_technical,
                     signal_ml, signal_onchain, signal_sentiment,
                     signal_orderbook, find_support_resistance)

STATE_FILE = "adaptive_state.json"
DESKTOP_DIR = os.path.expanduser("~/Desktop/ETH_自适应优化日志.txt")

# 默认权重
DEFAULT_WEIGHTS = {"tech": 0.35, "ml": 0.20, "orderbook": 0.15,
                   "onchain": 0.15, "sentiment": 0.15}


def get_signals():
    """采集所有信号，返回 {signal: score}"""
    result = {}
    # 优先拉实时 15m 数据
    CACHE_FILE = os.path.join(os.path.dirname(__file__), "eth_usdt_1h_2y.csv")
    try:
        df = fetch_data(200, "15m")
    except Exception as e:
        # Binance 失败时用缓存兜底
        if os.path.exists(CACHE_FILE):
            print(f"  ⚠ Binance {e}, 使用缓存数据")
            df = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True)
            df = df.tail(200)
        else:
            return None
    df = calc_indicators(df)
    if df.empty or len(df) < 10:
        print("  ⚠ 实时 15m 数据不足, 用 1h 缓存兜底")
        CACHE_FILE = os.path.join(os.path.dirname(__file__), "eth_usdt_1h_2y.csv")
        if os.path.exists(CACHE_FILE):
            df = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True).tail(200)
            df = calc_indicators(df)
        else:
            return None
    row = df.iloc[-1]
    result["price"] = round(row["close"], 2)
    result["timestamp"] = str(df.index[-1])
    
    tech = signal_technical(df)
    result["tech"] = round(sum(s*w for s,w,_ in tech) / sum(w for _,w,_ in tech), 3) if tech else 0
    
    # ML 用 1h 缓存数据（模型在 1h 上训练的）
    ml = {"score": 0, "prob": 0}
    if os.path.exists(CACHE_FILE):
        try:
            df_1h = pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True).tail(120)
            df_1h = calc_indicators(df_1h)
            ml = signal_ml(df_1h, 2)
        except:
            pass
    result["ml"] = ml.get("score", 0)
        
    ob = signal_orderbook()
    result["orderbook"] = ob.get("score", 0)
        
    on = signal_onchain()
    result["onchain"] = on.get("score", 0)
        
    sent = signal_sentiment()
    result["sentiment"] = sent.get("score", 0)
        
        # 支撑阻力
    # 支撑阻力用 15m 最近 96 根（约 24h）
    supports, resistances = find_support_resistance(df.tail(96), window=12)
    near_s = max([p for p, _ in supports if p < row["close"]] or [0])
    near_r = min([p for p, _ in resistances if p > row["close"]] or [0])
    result["support"] = round(near_s) if near_s else None
    result["resistance"] = round(near_r) if near_r else None
    return result


def calc_total(signals, weights):
    """加权综合评分"""
    s = sum(signals.get(k, 0) * weights[k] for k in weights)
    return round(s, 3)


def direction(score):
    if score > 0.15: return 1  # 看涨
    if score < -0.15: return -1  # 看跌
    return 0  # 震荡


def evaluate_last(state, signals):
    """评估上次预测的准确性"""
    if state.get("last_prediction") is None:
        return None
    
    last = state["last_prediction"]
    old_price = last["price"]
    new_price = signals["price"]
    actual = 1 if new_price > old_price else -1
    
    results = {}
    for signal_name in DEFAULT_WEIGHTS:
        pred_dir = direction(last["signals"].get(signal_name, 0))
        results[signal_name] = 1 if pred_dir == actual else 0
    
    results["total"] = 1 if last["direction"] == actual else 0
    results["actual"] = actual
    results["old_price"] = old_price
    results["new_price"] = new_price
    
    return results


def optimize_weights(state, eval_result):
    """根据最近准确率动态调整权重"""
    history = state.setdefault("accuracy_history", {s: [] for s in DEFAULT_WEIGHTS})
    history.setdefault("total", [])
    
    # 追加本次结果
    for signal in DEFAULT_WEIGHTS:
        history[signal].append(eval_result[signal])
    history["total"].append(eval_result["total"])
    
    # 滑动窗口: 只保留最近 30 条
    for key in history:
        history[key] = history[key][-30:]
    
    # 重新计算权重: 准确率高的信号权重更大
    accuracies = {}
    for signal in DEFAULT_WEIGHTS:
        h = history[signal]
        accuracies[signal] = sum(h) / len(h) if h else 0.5
    
    total_acc = sum(accuracies.values())
    if total_acc > 0:
        new_weights = {s: acc / total_acc for s, acc in accuracies.items()}
    else:
        new_weights = dict(DEFAULT_WEIGHTS)
    
    # 平滑更新（不要突变）
    old_weights = state.get("weights", DEFAULT_WEIGHTS)
    smoothed = {}
    for s in DEFAULT_WEIGHTS:
        smoothed[s] = round(old_weights[s] * 0.7 + new_weights[s] * 0.3, 3)
    
    return smoothed


def export_report(state, signals, eval_result, weights):
    """导出优化报告到桌面"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  ETH 自适应预测优化报告")
    lines.append(f"  时间: {now}")
    lines.append(f"  {'='*60}")
    
    # 上次预测验证
    if eval_result:
        dir_map = {1: "📈 看涨", -1: "📉 看跌", 0: "➖ 震荡"}
        lines.append(f"\n  上次预测验证:")
        lines.append(f"    预测时: ${eval_result['old_price']}  →  现在: ${eval_result['new_price']}")
        lines.append(f"    结果: {'✅ 正确' if eval_result['total'] else '❌ 错误'}")
        
        history = state.get("accuracy_history", {})
        total_hist = history.get("total", [])
        if total_hist:
            lines.append(f"    总体历史准确率: {sum(total_hist)}/{len(total_hist)} ({sum(total_hist)/len(total_hist)*100:.0f}%)")
    
    lines.append(f"\n  当前信号:")
    for s in DEFAULT_WEIGHTS:
        score = signals.get(s, 0)
        d = direction(score)
        d_str = "看涨 ↑" if d == 1 else ("看跌 ↓" if d == -1 else "震荡 —")
        lines.append(f"    {s:<12} {score:+.3f}  {d_str}")
    
    # 综合
    total_score = calc_total(signals, weights)
    total_dir = direction(total_score)
    d_str = "看涨 📈" if total_dir == 1 else ("看跌 📉" if total_dir == -1 else "震荡 ➖")
    lines.append(f"\n  综合评分: {total_score:+.3f}  →  {d_str}")
    
    lines.append(f"\n  当前权重:")
    for s, w in sorted(weights.items(), key=lambda x: -x[1]):
        lines.append(f"    {s:<12} {w:.3f}")
    
    # 最近准确率
    history = state.get("accuracy_history", {})
    lines.append(f"\n  各信号近30次准确率:")
    for s in DEFAULT_WEIGHTS:
        h = history.get(s, [])
        acc = sum(h)/len(h)*100 if h else 0
        bar = "█" * int(acc / 5)
        lines.append(f"    {s:<12} {bar} {acc:.0f}%  ({sum(h)}/{len(h)})")
    
    # 价格
    price = signals.get("price", 0)
    support = signals.get("support")
    resistance = signals.get("resistance")
    lines.append(f"\n  价格: ${price}")
    if support: lines.append(f"  支撑: ${support:.0f}")
    if resistance: lines.append(f"  阻力: ${resistance:.0f}")
    
    lines.append(f"\n  {'='*60}\n")
    
    report = "\n".join(lines)
    
    with open(DESKTOP_DIR, "a", encoding="utf-8") as f:
        f.write(report)
    
    print(report)


def main_loop(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true", help="持续运行，每 15m 一轮")
    args = parser.parse_args()
    
    # 加载状态
    state = {"weights": dict(DEFAULT_WEIGHTS), "last_prediction": None,
             "accuracy_history": {s: [] for s in DEFAULT_WEIGHTS}, "total_predictions": 0}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state.update(json.load(f))
    
    run = 0
    WAIT = 900 if args.daemon else 0
    while True:
        run += 1
        state["total_predictions"] = state.get("total_predictions", 0) + 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n  [{now}] 第 {run} 轮")
        sys.stdout.flush()

        # 1. 采集信号
        signals = get_signals()
        if signals is None:
            print("  ⚠ 信号采集失败，等待重试…")
            sys.stdout.flush()
            time.sleep(60)
            continue

        # 2. 评估上次预测
        eval_result = evaluate_last(state, signals)
        
        # 3. 优化权重
        weights = state.get("weights", dict(DEFAULT_WEIGHTS))
        if eval_result:
            weights = optimize_weights(state, eval_result)
            state["weights"] = weights
        
        # 4. 计算综合
        total_score = calc_total(signals, weights)
        total_dir = direction(total_score)
        
        # 5. 记录本次预测
        pred = {
            "time": now,
            "price": signals["price"],
            "direction": total_dir,
            "signals": {s: signals.get(s, 0) for s in DEFAULT_WEIGHTS},
            "score": total_score,
        }
        state["last_prediction"] = pred
        
        # 6. 导出报告到桌面
        export_report(state, signals, eval_result, weights)
        
        # 7. 保存状态
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2, default=str)
        sys.stdout.flush()

        if not args.daemon:
            break

        # 等待
        print(f"  等待 {WAIT} 秒到下一轮...\n")
        sys.stdout.flush()
        for remaining in range(WAIT, 0, -60):
            sys.stdout.write(f"\r  下次预测剩余: {remaining//60:>2} 分钟")
            sys.stdout.flush()
            time.sleep(60)
        print()
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true", help="持续运行")
    args = parser.parse_args()
    while True:
        try:
            main_loop(args)
            break  # non-daemon: exit after one run
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print(f"\n  ❌ 崩溃: {e}")
            print(f"  {err}")
            print(f"  10 秒后重启...\n")
            sys.stdout.flush()
            time.sleep(10)


if __name__ == "__main__":
    main()

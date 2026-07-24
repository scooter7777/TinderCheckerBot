#!/usr/bin/env python3
"""预测准确率回测 — 按时间顺序一步步测试"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from predict import (
    fetch_data, calc_indicators, signal_ml, signal_onchain,
    signal_sentiment, signal_technical, simple_sentiment_score
)
import numpy as np
import pandas as pd

TIMEFRAME = "1h"
TEST_CANDLES = 30          # 测试多少根
TRAIN_MIN = 60             # 最少训练数据

print(f"\n{'='*60}")
print(f"  预测准确率回测")
print(f"  周期: {TIMEFRAME}  |  测试 {TEST_CANDLES} 根  |  训练下限 {TRAIN_MIN}")
print(f"{'='*60}\n")

# 获取数据
df = fetch_data(TRAIN_MIN + TEST_CANDLES + 40, TIMEFRAME)
df = calc_indicators(df)
df = df.dropna()

total = len(df)
test_start = total - TEST_CANDLES
print(f"  总数据: {total} 根  |  训练: {test_start} 根  |  测试: {TEST_CANDLES} 根\n")

# 统计
results = []  # [(idx, pred_dir, actual_dir, correct)]

for i in range(test_start, total - 1):
    train_df = df.iloc[:i].copy()
    test_row = df.iloc[i]
    actual_next = df.iloc[i + 1]["close"]
    actual_dir = 1 if actual_next > test_row["close"] else -1

    # --- 技术面信号 ---
    tech = signal_technical(train_df)
    tech_score = sum(s * w for s, w, _ in tech) / sum(w for _, w, _ in tech)
    tech_dir = 1 if tech_score > 0.25 else (-1 if tech_score < -0.25 else 0)

    # --- ML 信号 ---
    horizon = 3
    ml_result = signal_ml(train_df, horizon)
    ml_score = ml_result.get("score", 0)
    ml_dir = 1 if ml_score > 0.05 else (-1 if ml_score < -0.05 else 0)

    # --- 链上信号 (只测最近 N 根) ---
    on_dir, sent_dir = 0, 0
    if i >= total - TEST_CANDLES + 5:  # 链上/情绪只测最后几根
        on = signal_onchain()
        on_dir = 1 if on.get("score", 0) > 0.1 else (-1 if on.get("score", 0) < -0.1 else 0)

    if i >= total - TEST_CANDLES + 5:
        sent = signal_sentiment()
        sent_dir = 1 if sent.get("score", 0) > 0.05 else (-1 if sent.get("score", 0) < -0.05 else 0)

    # 综合 (加权)
    total_score = tech_score * 1.5
    if ml_dir != 0:
        total_score += ml_score * 2.0
    if on_dir != 0:
        total_score += on.get("score", 0) * 0.8
    if sent_dir != 0:
        total_score += sent.get("score", 0) * 0.8

    total_w = 1.5
    if ml_dir != 0: total_w += 2.0
    if on_dir != 0: total_w += 0.8
    if sent_dir != 0: total_w += 0.8

    final_score = total_score / total_w if total_w > 0 else 0
    pred_dir = 1 if final_score > 0.15 else (-1 if final_score < -0.15 else 0)

    correct = pred_dir == actual_dir
    results.append((test_row.name, pred_dir, actual_dir, final_score, correct))

# 统计
total_tests = len(results)
correct_count = sum(1 for _, _, _, _, c in results if c)
accuracy = correct_count / total_tests * 100 if total_tests > 0 else 0

# 分类统计
ups = [(a, p) for _, p, a, _, _ in results]
correct_up = sum(1 for p, a in ups if p == 1 and a == 1)
correct_down = sum(1 for p, a in ups if p == -1 and a == -1)
total_up = sum(1 for _, a in ups if a == 1)
total_down = sum(1 for _, a in ups if a == -1)

print(f"  {'─'*52}")
print(f"  📊 总体预测准确率: {accuracy:.1f}%")
print(f"  ({correct_count}/{total_tests})")
print(f"  {'─'*52}\n")

print(f"  📋 分项:")
print(f"    上涨正确:  {correct_up}/{total_up}  ({correct_up/max(total_up,1)*100:.0f}%)")
print(f"    下跌正确:  {correct_down}/{total_down}  ({correct_down/max(total_down,1)*100:.0f}%)")

# 最近 10 根详细
print(f"\n  📋 最近 {min(10, total_tests)} 根详情:")
print(f"  {'时间':<18} {'预测':>6} {'实际':>6} {'评分':>8} {'正确':>4}")
print(f"  {'─'*44}")
for ts, pred, actual, score, correct in results[-10:]:
    p = "↑" if pred == 1 else ("↓" if pred == -1 else "—")
    a = "↑" if actual == 1 else "↓"
    c = "✅" if correct else "❌"
    print(f"  {str(ts)[:16]:<18} {p:>6} {a:>6} {score:>+7.2f}  {c:>4}")

print(f"\n  💡 准确率受样本量影响较大, 测试 {total_tests} 根数据仅供参考。\n")


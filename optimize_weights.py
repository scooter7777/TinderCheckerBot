#!/usr/bin/env python3
"""信号权重优化"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '.')

from predict import fetch_data, calc_indicators, signal_technical
from sklearn.ensemble import RandomForestClassifier

print("=" * 60)
print("  信号权重优化")
print("=" * 60)
print("  加载数据...")

df = fetch_data(200, '1h')
df = calc_indicators(df)
df['target_3'] = (df['close'].shift(-3) > df['close']).astype(int)
df = df.dropna().copy()

# 简单ML特征
ml_features = ['ret_1', 'ret_3', 'ret_5',
               'sma_cross', 'macd_hist', 'atr_pct',
               'vol_sma', 'bb_pct', 'stoch_k', 'williams_r']

for f in ml_features:
    if f not in df.columns:
        df[f] = 0.0

X = df[ml_features].values
y = df['target_3'].values
n = len(X)
print(f"  数据: {n} 根")
print()

def test_weights(w_tech, w_ml):
    """测试权重组合"""
    splits = [int(n * 0.5), int(n * 0.75), int(n * 0.9), n]
    chunks = [(splits[i], splits[i+1]) for i in range(len(splits)-1)]
    
    correct, total = 0, 0
    for train_end, test_end in chunks:
        if test_end - train_end < 10: continue
        
        model = RandomForestClassifier(n_estimators=80, max_depth=5, min_samples_leaf=10,
                                       class_weight='balanced', random_state=42)
        model.fit(X[:train_end], y[:train_end])
        
        for i in range(train_end, test_end):
            actual = y[i]
            features = df[ml_features].iloc[i:i+1].values
            prob = model.predict_proba(features)[0][1]
            ml_score = 2 * prob - 1
            
            tech = signal_technical(df.iloc[:i+1])
            ts = sum(s*w for s,w,_ in tech) / sum(w for _,w,_ in tech) if tech else 0
            
            combined = ts * w_tech + ml_score * w_ml
            pred = 1 if combined > 0.15 else (-1 if combined < -0.15 else 0)
            
            if pred != 0:
                total += 1
                if pred == actual:
                    correct += 1
    
    return correct / total * 100 if total > 0 else 0

# 测试组合
results = []
for w_tech in [0.3, 0.5, 0.7, 1.0]:
    for w_ml in [0.3, 0.5, 0.7, 1.0, 1.5]:
        acc = test_weights(w_tech, w_ml)
        results.append((w_tech, w_ml, acc))
        print(f"  技术 {w_tech:.1f}  ML {w_ml:.1f}  ->  {acc:.1f}%")

print()
results.sort(key=lambda x: -x[2])
print(f"  {'='*40}")
print(f"  Top 5:")
for w_tech, w_ml, acc in results[:5]:
    print(f"    技术 {w_tech:.1f}  ML {w_ml:.1f}  ->  {acc:.1f}%")
print(f"  {'='*40}")
best = results[0]
print(f"  🏆 最佳组合: 技术 {best[0]:.1f}  ML {best[1]:.1f}  ->  {best[2]:.1f}%")

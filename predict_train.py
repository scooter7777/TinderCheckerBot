#!/usr/bin/env python3
"""
ETH/USDT 高级预测模型训练
=========================
- 2年 1h 数据 (~17520 根)
- 40+ 特征
- Walk-forward 验证
- 导出模型供 predict.py 使用
"""

import argparse, os, pickle, sys, warnings
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# 数据缓存文件
DATA_CACHE = "eth_usdt_1h_2y.csv"
MODEL_FILE = "predict_model.pkl"

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, confusion_matrix
    HAS_SKLEARN = True
except:
    HAS_SKLEARN = False


def fetch_and_cache():
    """从 Binance 拉数据，缓存到本地 CSV"""
    if os.path.exists(DATA_CACHE):
        print(f"  📂 加载本地缓存: {DATA_CACHE}")
        df = pd.read_csv(DATA_CACHE, index_col=0, parse_dates=True)
        print(f"  ✓ {len(df)} 根 K 线 ({df.index[0]} → {df.index[-1]})")
        # 确保特征列都存在
    for col in FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    
    return df

    import ccxt
    ex = ccxt.binance({'options': {'defaultType': 'spot'}, 'timeout': 15000})
    since = ex.parse8601((datetime.now(timezone.utc) - timedelta(days=730)).isoformat())

    print("  ↓ 从 Binance 拉取 2 年 1h 数据…")
    all_ohlcv = []
    batch_start = since
    while True:
        batch = ex.fetch_ohlcv('ETH/USDT', '1h', since=batch_start, limit=1000)
        if not batch: break
        all_ohlcv.extend(batch)
        batch_start = batch[-1][0] + 1
        if len(batch) < 1000: break

    df = pd.DataFrame(all_ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
    df.set_index('ts', inplace=True)
    df.sort_index(inplace=True)
    df.to_csv(DATA_CACHE)
    print(f"  ✓ {len(df)} 根 K 线, 已缓存到 {DATA_CACHE}")
    # 确保特征列都存在
    for col in FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """生成 40+ 特征"""
    o, h, l, c, v = df['open'].values, df['high'].values, df['low'].values, df['close'].values, df['volume'].values
    n = len(df)

    # ---- 基础计算 ----
    df['hl'] = h - l
    df['hc'] = abs(h - c)
    df['lc'] = abs(l - c)

    # ---- 趋势 ----
    for p in [5, 10, 20, 50, 100]:
        df[f'sma_{p}'] = pd.Series(c, index=df.index).rolling(p).mean().values
        df[f'pct_sma_{p}'] = (c - df[f'sma_{p}']) / df[f'sma_{p}'] * 100
    for p in [12, 26]:
        df[f'ema_{p}'] = pd.Series(c, index=df.index).ewm(span=p, adjust=False).mean().values
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_sig'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_sig']
    df['sma_cross'] = np.where(df['sma_10'] > df['sma_50'], 1, -1)

    # ---- 动量 ----
    for p in [1, 3, 5, 10, 20]:
        df[f'ret_{p}'] = pd.Series(c, index=df.index).pct_change(p).values

    delta = pd.Series(c, index=df.index).diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    for p in [7, 14, 21]:
        ag = gain.rolling(p).mean()
        al = loss.rolling(p).mean()
        rs = ag / al.replace(0, np.nan)
        df[f'rsi_{p}'] = 100 - (100 / (1 + rs))

    # Stochastic
    for k in [14]:
        ll = pd.Series(l, index=df.index).rolling(k).min()
        hh = pd.Series(h, index=df.index).rolling(k).max()
        df['stoch_k'] = (c - ll) / (hh - ll) * 100
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()

    # Williams %R
    df['williams_r'] = (hh - c) / (hh - ll) * -100

    # ---- 波动率 ----
    tr = pd.concat([
        (df['high'] - df['low']).abs(),
        (df['high'] - df['close'].shift(1)).abs(),
        (df['low'] - df['close'].shift(1)).abs(),
    ], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    df['atr_pct'] = df['atr'] / c * 100

    # Bollinger
    for p in [20]:
        mid = pd.Series(c, index=df.index).rolling(p).mean()
        std = pd.Series(c, index=df.index).rolling(p).std()
        df['bb_upper'] = mid + 2 * std
        df['bb_lower'] = mid - 2 * std
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / mid
        df['bb_pct'] = (c - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

    # 历史波动率
    for p in [10, 20, 30]:
        ret = pd.Series(c, index=df.index).pct_change()
        df[f'hist_vol_{p}'] = ret.rolling(p).std() * np.sqrt(24 * 365) * 100

    # ---- 成交量 ----
    df['vol_sma'] = v / pd.Series(v, index=df.index).rolling(20).mean()
    df['vol_trend'] = pd.Series(v, index=df.index).ewm(span=10).mean() / pd.Series(v, index=df.index).ewm(span=50).mean()
    df['dvol'] = pd.Series(v * c, index=df.index) / pd.Series(v * c, index=df.index).rolling(20).mean()

    # ---- 价格形态 ----
    hl = np.where(h - l == 0, np.nan, h - l)
    df['body'] = abs(c - o) / hl
    df['upper_wick'] = (h - np.maximum(o, c)) / hl
    df['lower_wick'] = (np.minimum(o, c) - l) / hl
    df['gap'] = o / c  # 开盘/收盘比
    df['consecutive'] = np.sign(pd.Series(c, index=df.index).diff()).rolling(5).sum()

    # ---- 时间特征 ----
    if hasattr(df.index, 'hour'):
        df['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
        df['dow_sin'] = np.sin(2 * np.pi * df.index.dayofweek / 7)
        df['dow_cos'] = np.cos(2 * np.pi * df.index.dayofweek / 7)
    else:
        for col in ['hour_sin','hour_cos','dow_sin','dow_cos']:
            df[col] = 0.0

    # ---- 市场状态 (手动分档) ----
    vp = df['atr_pct'].values
    p25, p50, p75 = np.nanpercentile(vp, [25, 50, 75])
    regime = np.full(len(df), 1, dtype=float)
    regime[np.isnan(vp)] = np.nan
    regime[vp < p25 if not np.isnan(p25) else slice(0)] = 0
    regime[vp >= p75 if not np.isnan(p75) else slice(0)] = 2
    df['volatility_regime'] = regime
    df['trend_strength'] = abs(pd.Series(c, index=df.index) - pd.Series(c, index=df.index).rolling(50).mean()) / (pd.Series(c, index=df.index).rolling(50).std() + 1)

    # 确保特征列都存在
    for col in FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    
    return df


def train_model(df: pd.DataFrame, horizon: int = 3):
    """训练并验证模型"""
    print(f"\n  {'='*52}")
    print(f"  训练配置: 预测 +{horizon} 根  | 特征 {len(FEATURES)} 个")
    print(f"  {'='*52}\n")

    df_model = df[FEATURES + TARGETS].dropna().copy()
    X = df_model[FEATURES].values
    y = df_model[TARGETS[0]].values
    print(f"  有效样本: {len(X)}")

    # ---- Walk-forward 验证 ----
    n = len(X)
    # Walk-forward: train from start to train_end, test from train_end to test_end
    splits = [int(n * 0.5), int(n * 0.75), int(n * 0.9), n]
    chunks = [(splits[i], splits[i+1]) for i in range(len(splits)-1)]

    predictions = []
    actuals = []

    for train_end, test_end in chunks:
        if test_end - train_end < 100:
            continue

        X_train = X[:train_end]
        y_train = y[:train_end]
        X_test = X[train_end:test_end]
        y_test = y[train_end:test_end]

        model = RandomForestClassifier(
            n_estimators=200, max_depth=7,
            min_samples_leaf=10,
            class_weight='balanced',
            random_state=42, n_jobs=-1
        )
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        probs = model.predict_proba(X_test)

        predictions.extend(preds)
        actuals.extend(y_test)

    # ---- 统计 ----
    predictions = np.array(predictions)
    actuals = np.array(actuals)
    acc = accuracy_score(actuals, predictions)
    cm = confusion_matrix(actuals, predictions)
    tn, fp, fn, tp = cm.ravel()

    print(f"  📊 Walk-Forward 验证结果:")
    print(f"  {'─'*44}")
    print(f"  总测试样本:   {len(predictions)}")
    print(f"  准确率:       {acc*100:.1f}%")
    print(f"  {'─'*44}")
    print(f"  混淆矩阵:")
    print(f"    实际↓预测→  DOWN   UP")
    if tn + fp > 0:
        print(f"    DOWN       {tn:>5} {fp:>5}  (正确 {tn/(tn+fp)*100:.0f}%)")
    else:
        print(f"    DOWN       {tn:>5} {fp:>5}")
    if fn + tp > 0:
        print(f"    UP         {fn:>5} {tp:>5}  (正确 {tp/(fn+tp)*100:.0f}%)")
    else:
        print(f"    UP         {fn:>5} {tp:>5}")

    # ---- 特征重要性 ----
    model = RandomForestClassifier(n_estimators=200, max_depth=7, min_samples_leaf=10, random_state=42, n_jobs=-1)
    model.fit(X[:int(n*0.8)], y[:int(n*0.8)])

    importance = sorted(zip(FEATURES, model.feature_importances_), key=lambda x: -x[1])
    print(f"\n  📈 特征重要性 (Top 15):")
    print(f"  {'─'*44}")
    for name, imp in importance[:15]:
        bar = "█" * int(imp * 40)
        print(f"    {name:<20} {bar} {imp*100:.1f}%")

    # ---- 按市况分拆 ----
    test_idx = list(range(int(n * 0.5), n - 1))
    test_pred = model.predict(X[int(n*0.5):n-1])
    test_actual = y[int(n*0.5):n-1]

    # 获取测试段的 volatility regime
    regimes = []
    for i in test_idx:
        r = df_model.iloc[i].get('volatility_regime', 2)
        regimes.append(r)
    regimes = np.array(regimes)

    nz = n - int(n * 0.5)
    print(f"\n  📋 按波动率分拆 (测试集 {nz} 样本):")
    print(f"  {'─'*56}")
    print(f"  {'波动率':<10} {'样本':>6} {'正确':>6} {'准确率':>8}")
    print(f"  {'─'*56}")
    for regime_name, label in [("Low", 0), ("Normal", 1), ("Normal", 2), ("High", 3)]:
        mask = regimes == label
        if mask.sum() > 0:
            acc_r = accuracy_score(test_actual[mask], test_pred[mask])
            print(f"  {regime_name:<10} {mask.sum():>6} {(test_pred[mask]==test_actual[mask]).sum():>6} {acc_r*100:>7.1f}%")

    print(f"\n  💾 保存模型到 {MODEL_FILE}…")
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump({'model': model, 'features': FEATURES, 'accuracy': acc}, f)
    print(f"  ✓ 已保存\n")

    return model


# 特征和目标定义
FEATURES = [
    # 价格变化
    'ret_1', 'ret_3', 'ret_5', 'ret_10', 'ret_20',
    # 趋势
    'pct_sma_5', 'pct_sma_10', 'pct_sma_20', 'pct_sma_50', 'pct_sma_100',
    'sma_cross', 'macd_hist', 'macd',
    # 动量
    'rsi_7', 'rsi_14', 'rsi_21', 'stoch_k', 'stoch_d', 'williams_r',
    # 波动率
    'atr_pct', 'bb_width', 'bb_pct', 'hist_vol_10', 'hist_vol_20', 'hist_vol_30',
    # 成交量
    'vol_sma', 'vol_trend', 'dvol',
    # 价格形态
    'body', 'upper_wick', 'lower_wick', 'consecutive',
    # 时间
    'hour_sin', 'hour_cos', 'dow_sin', 'dow_cos',
    # 市场状态
    'volatility_regime', 'trend_strength',
]
TARGETS = ['target_3']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--horizon', type=int, default=3, help='预测未来多少根')
    parser.add_argument('--force-refetch', action='store_true', help='强制重新拉取数据')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  ETH/USDT 高级预测模型训练")
    print(f"{'='*60}\n")

    # 1. 加载数据
    if args.force_refetch and os.path.exists(DATA_CACHE):
        os.remove(DATA_CACHE)
    df = fetch_and_cache()

    # 2. 特征工程
    print("  🔧 生成特征…")
    df = add_features(df)

    # 3. 构造目标
    print(f"  构造目标 (预测 +{args.horizon} 根后收盘价是否上涨)…")
    df['target_3'] = (df['close'].shift(-args.horizon) > df['close']).astype(int)

    # 4. 训练
    model = train_model(df, args.horizon)


if __name__ == '__main__':
    main()

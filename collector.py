#!/usr/bin/env python3
"""
ETH/USDT 全维度数据采集器
=========================
每小时运行一次，保存: 价格, 技术面, ML, 盘口, 链上, 情绪
积累数据后可用 --retrain 重新训练模型

用法:
  python3 collector.py                # 采集一次
  python3 collector.py --loop         # 每小时采集一次
  python3 collector.py --retrain      # 用积累数据重新训练
"""

import argparse, os, sys, json, time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from predict import (
    fetch_data, calc_indicators, signal_technical, signal_ml,
    signal_onchain, signal_sentiment, signal_orderbook,
    find_support_resistance
)
from predict_train import add_features, FEATURES
from sklearn.ensemble import RandomForestClassifier

COLLECT_FILE = "collected_data.csv"
MODEL_FILE = "predict_model.pkl"

def collect_once():
    """采集所有维度数据，返回一条记录"""
    record = {"ts": datetime.now(timezone.utc).isoformat()}
    
    # 1. 价格 + 技术面
    try:
        df = fetch_data(120, "1h")
        df = calc_indicators(df)
        row = df.iloc[-1]
        record["price"] = round(row["close"], 2)
        record["open"] = round(row["open"], 2)
        record["high"] = round(row["high"], 2)
        record["low"] = round(row["low"], 2)
        record["volume"] = int(row["volume"])
        record["sma_trend"] = int(row.get("sma_trend", 0))
        record["rsi"] = round(row.get("rsi", 50), 1)
        record["macd_hist"] = round(row.get("macd_hist", 0), 2)
        record["atr_pct"] = round(row.get("atr_pct", 0), 2)
        
        # 支撑阻力
        supports, resistances = find_support_resistance(df.tail(48))
        near_s = [p for p, _ in supports if p < row["close"]]
        near_r = [p for p, _ in resistances if p > row["close"]]
        record["support"] = round(max(near_s), 0) if near_s else 0
        record["resistance"] = round(min(near_r), 0) if near_r else 0
        
        # 技术面评分
        tech = signal_technical(df)
        record["tech_score"] = round(sum(s*w for s,w,_ in tech) / sum(w for _,w,_ in tech), 3)
    except Exception as e:
        record["price"] = 0; record["tech_score"] = 0
    
    # 2. ML
    try:
        ml = signal_ml(df, 3) if 'df' in dir() else {"score": 0, "prob": 0}
        record["ml_score"] = ml.get("score", 0)
        record["ml_prob"] = ml.get("prob", 0)
    except:
        record["ml_score"] = 0; record["ml_prob"] = 0
    
    # 3. 盘口
    try:
        ob = signal_orderbook()
        record["ob_score"] = ob.get("score", 0)
        record["ob_ratio"] = ob.get("ratio", 0)
        record["ob_bid"] = ob.get("bid_depth", 0)
        record["ob_ask"] = ob.get("ask_depth", 0)
    except:
        record["ob_score"] = 0; record["ob_ratio"] = 0
        record["ob_bid"] = 0; record["ob_ask"] = 0
    
    # 4. 链上
    try:
        on = signal_onchain()
        record["onchain_score"] = on.get("score", 0)
        record["gas"] = on.get("gas_usd", 0)
        record["tx_24h"] = on.get("tx_24h", 0)
    except:
        record["onchain_score"] = 0; record["gas"] = 0; record["tx_24h"] = 0
    
    # 5. 情绪
    try:
        sent = signal_sentiment()
        record["sentiment_score"] = sent.get("score", 0)
        record["articles"] = sent.get("articles", 0)
    except:
        record["sentiment_score"] = 0; record["articles"] = 0
    
    # 6. 综合
    scores = [
        record.get("tech_score", 0) * 0.4,
        record.get("ml_score", 0) * 0.2,
        record.get("ob_score", 0) * 0.15,
        record.get("onchain_score", 0) * 0.15,
        record.get("sentiment_score", 0) * 0.1,
    ]
    record["total_score"] = round(sum(scores), 3)
    record["direction"] = 1 if record["total_score"] > 0.2 else (-1 if record["total_score"] < -0.2 else 0)
    
    record["status"] = "OK"
    return record


def save_record(record):
    """追加保存一条记录"""
    df = pd.DataFrame([record])
    mode = "a" if os.path.exists(COLLECT_FILE) else "w"
    header = not os.path.exists(COLLECT_FILE)
    df.to_csv(COLLECT_FILE, mode=mode, header=header, index=False)


def retrain_model():
    """用积累的数据重新训练模型"""
    print(f"\n  {'='*52}")
    print(f"  使用积累数据重新训练模型")
    print(f"  {'='*52}\n")
    
    if not os.path.exists(COLLECT_FILE):
        print("  ✗ 无积累数据，请先运行采集")
        return
    
    data = pd.read_csv(COLLECT_FILE)
    print(f"  加载 {len(data)} 条记录")
    
    # 需要结合原始OHLCV数据来训练
    # 我们从已缓存的2年数据中提取对应时间点的特征
    csv_cache = "eth_usdt_1h_2y.csv"
    if not os.path.exists(csv_cache):
        print("  ✗ 需要先运行 predict_train.py 生成缓存数据")
        return
    
    ohlcv = pd.read_csv(csv_cache, index_col=0, parse_dates=True)
    
    # 为每条采集数据匹配最近的OHLCV记录
    features_list = []
    targets = []
    
    for _, rec in data.iterrows():
        try:
            rec_time = pd.to_datetime(rec["ts"])
            # 找最近的OHLCV记录
            idx = ohlcv.index.get_indexer([rec_time], method="nearest")
            if idx[0] < 0 or idx[0] >= len(ohlcv):
                continue
            
            # 取该点附近的一段数据来计算特征
            lookback = 80
            start = max(0, idx[0] - lookback)
            chunk = ohlcv.iloc[start:idx[0]+1].copy()
            if len(chunk) < 30:
                continue
            
            chunk = add_features(chunk)
            last = chunk.iloc[-1]
            
            # 基础特征
            feat = {}
            for f in FEATURES:
                if f in chunk.columns:
                    feat[f] = last[f]
                else:
                    feat[f] = 0
            
            # 新增维度特征
            feat["ob_ratio"] = rec.get("ob_ratio", 0)
            feat["onchain_score"] = rec.get("onchain_score", 0)
            feat["sentiment_score"] = rec.get("sentiment_score", 0)
            feat["gas"] = rec.get("gas", 0)
            feat["articles"] = rec.get("articles", 0)
            
            features_list.append(feat)
            
            # 目标: 3小时后涨跌
            future_idx = min(idx[0] + 3, len(ohlcv) - 1)
            target = 1 if ohlcv.iloc[future_idx]["close"] > ohlcv.iloc[idx[0]]["close"] else 0
            targets.append(target)
        except:
            continue
    
    if len(features_list) < 50:
        print(f"  ✗ 有效样本仅 {len(features_list)} 条，需要至少 50 条")
        return
    
    X = pd.DataFrame(features_list).fillna(0).values
    y = np.array(targets)
    
    print(f"  有效样本: {len(X)}")
    
    # 训练
    model = RandomForestClassifier(
        n_estimators=200, max_depth=7, min_samples_leaf=10,
        class_weight="balanced", random_state=42, n_jobs=-1
    )
    model.fit(X, y)
    
    # 保存
    feature_names = list(features_list[0].keys())
    with open(MODEL_FILE, "wb") as f:
        import pickle
        pickle.dump({"model": model, "features": feature_names}, f)
    
    print(f"  ✓ 模型保存到 {MODEL_FILE}")
    print(f"  新增特征: ob_ratio, onchain_score, sentiment_score, gas, articles")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="循环采集")
    parser.add_argument("--interval", type=int, default=300, help="采集间隔(秒), 默认300(5分钟)")
    parser.add_argument("--count", type=int, default=0, help="采集次数, 0=不限")
    parser.add_argument("--retrain", action="store_true", help="用积累数据重新训练")
    args = parser.parse_args()
    
    if args.retrain:
        retrain_model()
        sys.exit(0)
    
    print(f"\n  ETH/USDT 全维度数据采集")
    
    run = 1
    while True:
        print(f"  第 {run} 次采集 [{datetime.now().strftime('%H:%M')}]...")
        rec = collect_once()
        save_record(rec)
        
        price = rec.get("price", 0)
        score = rec.get("total_score", 0)
        dir_map = {1: "📈 看涨", -1: "📉 看跌", 0: "➖ 震荡"}
        print(f"    ${price}  评分 {score:+.3f}  {dir_map.get(rec['direction'], '?')}")
        print(f"    盘口比 {rec.get('ob_ratio', 0):.1f}  链上 {rec.get('onchain_score', 0):+.2f}  情绪 {rec.get('sentiment_score', 0):+.2f}")
        
        if not args.loop:
            break
        
        print(f"    等待 {args.interval} 秒...\n")
        time.sleep(args.interval)
        run += 1
        if args.count > 0 and run > args.count: break
    
    print(f"\n  数据已保存到 {COLLECT_FILE}")
    print(f"  积累足够后运行: python3 collector.py --retrain\n")

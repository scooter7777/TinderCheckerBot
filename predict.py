#!/usr/bin/env python3
"""
ETH/USDT 多信号预测工具 (ML + 链上 + 情绪 + 技术面)
===================================================
用法:
  python3 predict.py
  python3 predict.py --timeframe 15m --horizon 4
  python3 predict.py --no-ml --no-onchain --no-sentiment  # 只保留技术面
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import RandomForestClassifier
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def parse_args():
    p = argparse.ArgumentParser(description="ETH/USDT 多信号预测")
    p.add_argument("--timeframe", default="1h", help="K 线周期")
    p.add_argument("--lookback", type=int, default=120, help="分析历史 K 线数")
    p.add_argument("--horizon", type=int, default=2, help="预测未来多少根 K 线")
    p.add_argument("--no-ml", action="store_true", help="禁用 ML 预测")
    p.add_argument("--no-onchain", action="store_true", help="禁用链上数据")
    p.add_argument("--no-sentiment", action="store_true", help="禁用新闻情绪")
    p.add_argument("--no-orderbook", action="store_true", help="禁用盘口数据")
    return p.parse_args()


# ---------------------------------------------------------------------------
# 数据获取
# ---------------------------------------------------------------------------

def fetch_data(lookback: int, timeframe: str = "1h") -> pd.DataFrame:
    import requests
    print(f"  ↓ 正在拉取 ETH/USDT {timeframe} 数据…")
    
    # 时间框架 -> 毫秒
    tf_ms = {"15m": 15*60*1000, "1h": 60*60*1000, "4h": 4*60*60*1000, "1d": 24*60*60*1000}
    limit = 1000
    interval_ms = tf_ms.get(timeframe, 60*60*1000)
    lookback_ms = lookback * interval_ms * 2
    
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - lookback_ms
    
    all_ohlcv = []
    batch_start = start_ms
    while True:
        url = f"https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval={timeframe}&startTime={batch_start}&limit={limit}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            batch = resp.json()
        except Exception as e:
            print(f"  ⚠ 请求失败: {e}")
            time.sleep(2)
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                batch = resp.json()
            except:
                print("  ⚠ 重试也失败, 跳过本批")
                break
        if not batch or len(batch) == 0:
            break
        all_ohlcv.extend(batch)
        # Binance 返回 [time, O, H, L, C, V, close_time, qav, num_trades, taker_bv, taker_qv, ignore]
        last_time = batch[-1][0]
        batch_start = last_time + 1
        if len(batch) < limit:
            break
    
    ohlcv = all_ohlcv
    if not ohlcv:
        print("  ⚠ 未获取到任何 K 线数据")
        return pd.DataFrame()
    print(f"  ✓ {len(ohlcv)} 根 K 线 (最新 {pd.to_datetime(ohlcv[-1][0], unit='ms', utc=True)})")
    # Binance raw format: [time, O, H, L, C, V, ...]
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume", "ct","qa","nt","tbv","tqv","ig"])
    df = df[["timestamp","open","high","low","close","volume"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    if len(df) < 50:
        print("  ⚠ 获取数据不足, 返回空DataFrame")
        return pd.DataFrame()
    return df.tail(lookback + 50)  # 多取一些用于计算指标


# ---------------------------------------------------------------------------
# 技术指标
# ---------------------------------------------------------------------------

def calc_indicators(df: pd.DataFrame):
    df["sma7"] = df["close"].rolling(7).mean()
    df["sma25"] = df["close"].rolling(25).mean()
    df["sma_trend"] = np.where(df["sma7"] > df["sma25"], 1, -1)

    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.rolling(14).mean()
    avg_l = loss.rolling(14).mean()
    rs = avg_g / avg_l.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_sig"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]

    # 布林带
    df["bb_mid"] = df["close"].rolling(20).mean()
    df["bb_std"] = df["close"].rolling(20).std()
    df["bb_width"] = (df["bb_mid"] + 2 * df["bb_std"] - (df["bb_mid"] - 2 * df["bb_std"])) / df["bb_mid"]
    df["bb_pos"] = (df["close"] - df["bb_mid"]) / (df["bb_std"] * 2)

    # 波动率
    tr = pd.concat([
        (df["high"] - df["low"]).abs(),
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr"] / df["close"] * 100

    # 价格变化率
    for p in [1, 3, 5]:
        df[f"price_change_{p}"] = df["close"].pct_change(p)
    df["volume_change"] = df["volume"].pct_change(3)

    return df


# ---------------------------------------------------------------------------
# 信号 1: 机器学习模型
# ---------------------------------------------------------------------------

def signal_ml(df: pd.DataFrame, horizon: int) -> dict:
    """用 RandomForest 预测接下来 direction 的概率"""
    if not HAS_SKLEARN:
        return {"signal": 0, "prob": 0, "detail": "sklearn 未安装"}

    features = ["price_change_1", "price_change_3", "price_change_5",
                "rsi", "macd_hist", "atr_pct",
                "volume_change", "sma_trend", "bb_pos", "bb_width"]

    df_ml = df[features + ["close"]].dropna().copy()
    if len(df_ml) < 30:
        return {"signal": 0, "prob": 0, "detail": "数据不足"}

    # 构造目标: horizon 根后收盘价是否高于当前
    df_ml["target"] = (df_ml["close"].shift(-horizon) > df_ml["close"]).astype(int)
    df_ml = df_ml.dropna()

    X = df_ml[features].values
    y = df_ml["target"].values

    if len(X) < 20:
        return {"signal": 0, "prob": 0, "detail": "训练数据不足"}

    split = int(len(X) * 0.7)
    X_train, y_train = X[:split], y[:split]

    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    # 预测最新
    latest = df_ml[features].iloc[-1:].values
    prob_up = model.predict_proba(latest)[0][1]
    pred = model.predict(latest)[0]

    score = 2 * prob_up - 1  # 0~1映射到 -1~+1
    signal = 1 if pred == 1 else -1
    return {
        "signal": signal,
        "prob": round(prob_up, 2),
        "score": round(score, 2),
        "detail": f"ML 预测涨概率 {prob_up:.0%}",
    }


# ---------------------------------------------------------------------------
# 信号 2: 链上数据
# ---------------------------------------------------------------------------

def signal_onchain() -> dict:
    """从公开 API 获取 ETH 链上数据 (Gas, 交易数等)"""
    if not HAS_REQUESTS:
        return {"signal": 0, "detail": "requests 未安装"}

    try:
        r = requests.get("https://api.blockchair.com/ethereum/stats", timeout=10)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        data = r.json()["data"]

        tx_count_24h = int(data.get("transactions_24h", 0) or 0)
        gas_median = data.get("gas_price_median_usd", "?")
        try:
            gas_price = float(gas_median)
        except:
            gas_price = 0.5

        # Gas 判断
        # tx_per_gas not needed
        # 低 gas + 高交易量 = 健康网络 = 看涨
        if gas_price < 0.3 and tx_count_24h > 1_000_000:
            score = 0.5
            detail = f"Gas 低(${gas_price:.2f}), 交易活跃"
        elif gas_price > 1.5:
            score = -0.3
            detail = f"Gas 偏高(${gas_price:.2f}), 网络拥堵"
        else:
            score = 0.2
            detail = f"Gas 正常(${gas_price:.2f})"

        return {
            "signal": 1 if score > 0 else (-1 if score < 0 else 0),
            "score": score,
            "detail": detail,
            "gas_usd": round(gas_price, 2),
            "tx_24h": tx_count_24h,
        }
    except Exception as e:
        return {"signal": 0, "detail": f"链上 API 失败: {e}"}


# ---------------------------------------------------------------------------
# 信号 3: 新闻情绪
# ---------------------------------------------------------------------------

def simple_sentiment_score(text: str) -> float:
    """简单关键词情绪评分"""
    text_lower = text.lower()
    bullish = ["surge", "rally", "gain", "bullish", "upgrade", "launch",
               "partnership", "adoption", "etf", "approve", "breakthrough",
               "positive", "soar", "jump", "新高"]
    bearish = ["crash", "drop", "fall", "bearish", "hack", "ban",
               "restriction", "regulation", "fear", "sell-off", "decline",
               "negative", "slump", "plunge", "危机", "大跌"]
    score = 0
    for w in bullish:
        if w in text_lower:
            score += 0.15
    for w in bearish:
        if w in text_lower:
            score -= 0.15
    return max(-1, min(1, score))


def signal_sentiment() -> dict:
    """获取 ETH 新闻 (Google News RSS) 并做情绪分析"""
    if not HAS_REQUESTS:
        return {"signal": 0, "score": 0, "detail": "requests 未安装"}

    import xml.etree.ElementTree as ET

    try:
        r = requests.get(
            "https://news.google.com/rss/search?q=ethereum+crypto&hl=en-US&gl=US&ceid=US:en",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=10,
        )
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        if not items:
            return {"signal": 0, "score": 0, "detail": "无新闻"}

        scores = []
        for item in items[:12]:
            title = (item.findtext("title") or "")
            desc = (item.findtext("description") or "")[:200]
            s = simple_sentiment_score(title + " " + desc)
            if abs(s) > 0.01:
                scores.append(s)

        avg = np.mean(scores) if scores else 0
        return {
            "signal": 1 if avg > 0.05 else (-1 if avg < -0.05 else 0),
            "score": round(avg, 2),
            "articles": len(scores),
            "detail": f"新闻情绪 {avg:+.2f} ({len(scores)} 篇)",
        }
    except Exception as e:
        return {"signal": 0, "score": 0, "detail": f"新闻 RSS 失败: {e}"}


# ---------------------------------------------------------------------------
# 传统技术面信号 (精简版)
# ---------------------------------------------------------------------------

def signal_technical(df: pd.DataFrame) -> list:
    row = df.iloc[-1]
    signals = []

    trend = row.get("sma_trend", 0)
    signals.append((1.0 if trend == 1 else -1.0, 1.5,
                    "SMA 多头排列" if trend == 1 else "SMA 空头排列"))

    rsi = row.get("rsi", 50)
    if rsi < 30:
        signals.append((1.0, 1.0, "RSI 超卖"))
    elif rsi > 70:
        signals.append((-1.0, 1.0, "RSI 超买"))
    elif rsi < 40:
        signals.append((0.5, 0.8, "RSI 偏空"))
    elif rsi > 60:
        signals.append((-0.5, 0.8, "RSI 偏多"))
    else:
        signals.append((0.0, 0.5, "RSI 中性"))

    mh = row.get("macd_hist", 0)
    if mh > 0:
        signals.append((0.6, 1.0, "MACD 多头"))
    elif mh < 0:
        signals.append((-0.6, 1.0, "MACD 空头"))

    return signals


def signal_orderbook() -> dict:
    """获取实时盘口深度信号"""
    if not HAS_REQUESTS:
        return {"signal": 0, "score": 0, "detail": "requests 未安装"}
    try:
        import requests as req
        resp = req.get("https://api.binance.com/api/v3/depth?symbol=ETHUSDT&limit=50", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        bids = [[float(p), float(q)] for p, q in data["bids"]]
        asks = [[float(p), float(q)] for p, q in data["asks"]]
        bid_val = sum(p * a for p, a in bids[:20])
        ask_val = sum(p * a for p, a in asks[:20])
        if bid_val + ask_val == 0:
            return {"signal": 0, "score": 0, "detail": "盘口数据为空"}
        ratio = bid_val / ask_val
        walls = []
        for p, a in bids[:10]:
            if p * a > 300_000: walls.append(f"买墙 ${p:.0f}")
        for p, a in asks[:10]:
            if p * a > 300_000: walls.append(f"卖墙 ${p:.0f}")
        if ratio < 0.3:
            score, signal = max(-0.9, -0.8 + ratio * 0.5), -1
        elif ratio < 0.7:
            score, signal = -0.2, -1
        elif ratio > 3:
            score, signal = min(0.7, 0.3 + ratio * 0.05), 1
        elif ratio > 1.5:
            score, signal = 0.2, 1
        else:
            score, signal = 0.0, 0
        detail = f"盘口买卖比 {ratio:.2f}"
        if walls: detail += " | " + ", ".join(walls[:2])
        return {"signal": signal, "score": round(score, 2), "detail": detail,
                "ratio": round(ratio, 2), "bid_depth": int(bid_val), "ask_depth": int(ask_val)}
    except Exception as e:
        return {"signal": 0, "score": 0, "detail": f"盘口数据失败: {e}"}


# ---------------------------------------------------------------------------
# 主预测
# ---------------------------------------------------------------------------

def predict(df: pd.DataFrame, horizon: int, args) -> dict:
    signals = []  # [(score, weight, name)]

    # 1. 技术面
    tech_signals = signal_technical(df)
    signals.extend(tech_signals)

    # 2. ML
    if not args.no_ml:
        ml = signal_ml(df, horizon)
        ml_score = ml.get("score", 0)
        if abs(ml_score) > 0.05:
            signals.append((ml_score, 0.5, ml["detail"]))
        else:
            signals.append((0, 0.5, f"ML: {ml.get('detail', 'n/a')}"))

    # 3. 链上
    if not args.no_onchain:
        on = signal_onchain()
        signals.append((on.get("score", 0), 0.8, on.get("detail", "链上数据 N/A")))

    # 4. 新闻情绪
    if not args.no_sentiment:
        sent = signal_sentiment()
        signals.append((sent.get("score", 0), 0.8, sent.get("detail", "新闻情绪 N/A")))

    if not args.no_orderbook:
        ob = signal_orderbook()
        signals.append((ob.get("score", 0), 1.2, ob.get("detail", "盘口数据 N/A")))

    # 计算总分
    total_w = sum(w for _, w, _ in signals)
    total_s = sum(s * w for s, w, _ in signals) / total_w if total_w > 0 else 0

    scores = [s for s, _, _ in signals]
    agreement = 1 - np.std(scores) if len(scores) > 1 else 0.5
    confidence = max(0, min(1, agreement))

    if total_s > 0.25:
        direction = "看涨 📈"
    elif total_s < -0.25:
        direction = "看跌 📉"
    else:
        direction = "震荡 ➖"

    return {
        "direction": direction,
        "score": round(total_s, 3),
        "confidence": round(confidence, 2),
        "signals": signals,
        "close": df.iloc[-1]["close"],
    }


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def find_support_resistance(df: pd.DataFrame, window: int = 8, min_touches: int = 2) -> tuple[list, list]:
    """识别支撑位和阻力位"""
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    resist_candidates = []
    support_candidates = []

    for i in range(window, n - window):
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, window + 1)):
            resist_candidates.append(highs[i])
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, window + 1)):
            support_candidates.append(lows[i])

    def cluster(candidates, tol_pct=0.015):
        if not candidates:
            return []
        cands = sorted(candidates)
        clusters, cur = [], [cands[0]]
        for c in cands[1:]:
            avg = sum(cur) / len(cur)
            if abs(c - avg) / avg < tol_pct:
                cur.append(c)
            else:
                clusters.append((sum(cur) / len(cur), len(cur)))
                cur = [c]
        clusters.append((sum(cur) / len(cur), len(cur)))
        return [c for c in clusters if c[1] >= min_touches]

    return cluster(support_candidates), cluster(resist_candidates)


def plot_prediction(df: pd.DataFrame, result: dict):
    """生成带支撑 / 阻力线的预测图表"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    plt.rcParams["figure.dpi"] = 120

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(df.index, df["close"], color="#1a1a2e", linewidth=0.9, label="ETH/USDT")

    # S/R 线
    supports, resistances = find_support_resistance(df)
    for price, _ in supports:
        ax.axhline(y=price, color="#00c853", linestyle="--", alpha=0.5, linewidth=1.2)
        ax.text(df.index[0], price * 0.998, f"S {price:.0f}",
                color="#00c853", fontsize=9, alpha=0.8, fontweight="bold")
    for price, _ in resistances:
        ax.axhline(y=price, color="#ff1744", linestyle="--", alpha=0.5, linewidth=1.2)
        ax.text(df.index[0], price * 1.002, f"R {price:.0f}",
                color="#ff1744", fontsize=9, alpha=0.8, fontweight="bold")

    # 当前价格标记
    close = result["close"]
    last_idx = df.index[-1]
    ax.scatter(last_idx, close, color="#ff9100", s=120, zorder=6, marker="o",
               edgecolors="white", linewidth=2)
    ax.annotate(f"${close:.2f}", xy=(last_idx, close),
                xytext=(10, 10), textcoords="offset points",
                fontsize=11, fontweight="bold", color="#ff9100")

    # 预测方向
    dir_symbol = {"看涨 📈": "↑", "看跌 📉": "↓", "震荡 ➖": "→"}
    ax.set_title(
        f"ETH/USDT 预测 — {result['direction']}  |  "
        f"评分 {result['score']:+.2f}  |  置信度 {result['confidence']:.0%}",
        fontsize=13, fontweight="bold"
    )
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.15)

    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    plt.tight_layout()
    out = "predict_result.png"
    plt.savefig(out, bbox_inches="tight")
    print(f"  📊 预测图表: {out}")
    plt.close()


def main():
    args = parse_args()

    print(f"\n{'='*60}")
    print(f"  ETH/USDT 多信号预测")
    print(f"  周期: {args.timeframe}  |  预测 +{args.horizon}")
    enabled = []
    if not args.no_ml: enabled.append("ML")
    if not args.no_onchain: enabled.append("链上")
    if not args.no_sentiment: enabled.append("情绪")
    if not args.no_orderbook: enabled.append("盘口")
    print(f"  信号源: {' + '.join(enabled)} + 技术面")
    print(f"{'='*60}\n")

    df = fetch_data(args.lookback, args.timeframe)
    if len(df) < 30:
        print("  ✗ 数据不足")
        sys.exit(1)

    df = calc_indicators(df)
    result = predict(df, args.horizon, args)

    print(f"  最新: {df.index[-1]}  |  收盘: ${result['close']:.2f}\n")
    # 画图
    plot_prediction(df, result)

    print(f"  {'─'*52}")
    print(f"  📊 预测: {result['direction']}")
    print(f"  综合评分:  {result['score']:+.3f}  (-1 ~ +1)")
    print(f"  置信度:    {result['confidence']:.0%}")
    print(f"  {'─'*52}\n")

    print(f"  📋 信号明细:")
    for score, weight, name in result["signals"]:
        bar = "█" * int(abs(score) * 8) + "░" * (8 - int(abs(score) * 8))
        sym = "🟢" if score > 0 else ("🔴" if score < 0 else "⚪")
        print(f"    {sym} {name:<30} {bar} {score:+.2f} (×{weight:.0f})")
    print()

    print(f"  💡 提示: 置信度 < 50% 时请谨慎参考。\n")


if __name__ == "__main__":
    main()

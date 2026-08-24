#!/usr/bin/env python3
"""Kairo Hub 本地服务：复刻 KairoTrend 分析终端，但全部使用真实数据。

服务端负责:
  1. 从币安 USDT-M 合约接口拉取真实 K 线
  2. 计算技术指标 / 多周期结构 / 筹码分布 / 支撑阻力 / 形态
  3. 生成可解释的交易计划(方向/入场/触发/止损/止盈/置信度/理由)
  4. 渲染包含实时快照的 HTML 页面(浏览器沙箱不支持 fetch, 数据嵌入页面)

运行:
  python3 server.py [--port 8766]
"""
import argparse
import json
import math
import os
import queue
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import requests

try:
    from futures_signals import fetch_futures, score_funding, score_oi, score_taker, score_ls
except Exception:
    fetch_futures = score_funding = score_oi = score_taker = score_ls = None

HERE = os.path.dirname(os.path.abspath(__file__))
FAPI = "https://fapi.binance.com"
HL_API = "https://api.hyperliquid.xyz"

HL_INTERVALS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000,
    "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
}
SYMBOL_TO_HL = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
    "BNBUSDT": "BNB", "XRPUSDT": "XRP", "DOGEUSDT": "DOGE",
}
SOURCES = ("binance", "hyperliquid")

VERIFY_LOCK = threading.Lock()
VERIFY_SESSIONS = {}
VERIFY_RATE = {}
CODE_TTL = 300
MAX_ATTEMPTS = 5
SEND_INTERVAL = 60


def valid_phone(phone):
    return bool(re.fullmatch(r"1[3-9]\d{9}", phone or ""))


def mask_phone(phone):
    return f"{phone[:3]}****{phone[-4:]}"


def new_verify_session(phone):
    req_id = secrets.token_hex(8)
    code = f"{secrets.randbelow(1000000):06d}"
    session = {
        "phone": phone,
        "code": code,
        "expires": time.time() + CODE_TTL,
        "attempts": 0,
        "status": "pending",
        "events": [],
        "listeners": [],
    }
    with VERIFY_LOCK:
        VERIFY_SESSIONS[req_id] = session
    return req_id, session


def add_verify_event(session, stage, text, extra=None):
    ev = {"stage": stage, "text": text, "ts": now_cn()}
    if extra:
        ev.update(extra)
    session["events"].append(ev)
    for q in list(session.get("listeners", [])):
        try:
            q.put(ev)
        except Exception:
            pass


def send_code_progress(req_id, phone):
    session = VERIFY_SESSIONS.get(req_id)
    if not session:
        return
    time.sleep(0.25)
    add_verify_event(session, "accepted", "请求已接收")
    time.sleep(0.40)
    add_verify_event(session, "validated", f"手机号 {mask_phone(phone)} 校验通过")
    time.sleep(0.45)
    add_verify_event(session, "generated", "6 位验证码已生成")
    time.sleep(0.35)
    add_verify_event(session, "sent", "验证码已通过演示短信通道送达",
                     extra={"demo_code": session["code"]})
    session["sent_at"] = time.time()

SYMBOLS = [
    ("BTCUSDT", "BTC/USDT"),
    ("ETHUSDT", "ETH/USDT"),
    ("SOLUSDT", "SOL/USDT"),
    ("BNBUSDT", "BNB/USDT"),
    ("XRPUSDT", "XRP/USDT"),
    ("DOGEUSDT", "DOGE/USDT"),
]
TIMEFRAMES = [
    ("1m", "1分钟", 15),
    ("3m", "3分钟", 30),
    ("5m", "5分钟", 45),
    ("15m", "15分钟", 60),
    ("30m", "30分钟", 90),
    ("1h", "1小时", 120),
    ("4h", "4小时", 180),
    ("1d", "1天", 300),
]
MTF_TIMEFRAMES = [("15m", "15分钟"), ("1h", "1小时"), ("4h", "4小时"), ("1d", "1天")]

_KLINE_CACHE = {}
_KLINE_CACHE_LOCK = threading.Lock()
_FUT_CACHE = {}
_FUT_CACHE_LOCK = threading.Lock()


def now_cn():
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def get_json(url, params=None, timeout=15):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def hl_post(payload, timeout=15):
    r = requests.post(f"{HL_API}/info", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def fetch_klines(symbol, interval, limit=500, force=False):
    key = f"{symbol}:{interval}:{limit}"
    now = time.time()
    with _KLINE_CACHE_LOCK:
        hit = _KLINE_CACHE.get(key)
        if hit and not force and now - hit["ts"] < 12:
            return hit["data"]
    data = get_json(f"{FAPI}/fapi/v1/klines",
                    {"symbol": symbol, "interval": interval, "limit": limit})
    rows = [{
        "t": int(k[0]), "o": float(k[1]), "h": float(k[2]),
        "l": float(k[3]), "c": float(k[4]), "v": float(k[5]),
    } for k in data]
    with _KLINE_CACHE_LOCK:
        _KLINE_CACHE[key] = {"ts": now, "data": rows}
    return rows


def fetch_hl_klines(symbol, interval, limit=500, force=False):
    coin = SYMBOL_TO_HL.get(symbol)
    if coin is None or interval not in HL_INTERVALS:
        raise ValueError(f"Hyperliquid 不支持 {symbol} {interval}")
    key = f"HL:{symbol}:{interval}:{limit}"
    now = time.time()
    with _KLINE_CACHE_LOCK:
        hit = _KLINE_CACHE.get(key)
        if hit and not force and now - hit["ts"] < 12:
            return hit["data"]
    end_ms = int(now * 1000)
    start_ms = end_ms - limit * HL_INTERVALS[interval]
    data = hl_post({
        "type": "candleSnapshot",
        "req": {"coin": coin, "interval": interval,
                "startTime": start_ms, "endTime": end_ms},
    })
    rows = [{
        "t": int(k["t"]),
        "o": float(k["o"]),
        "h": float(k["h"]),
        "l": float(k["l"]),
        "c": float(k["c"]),
        "v": float(k["v"]),
    } for k in data]
    with _KLINE_CACHE_LOCK:
        _KLINE_CACHE[key] = {"ts": now, "data": rows}
    return rows


def fetch_inst(symbol, source="binance"):
    now = time.time()
    cache_key = f"{symbol}:{source}"
    with _FUT_CACHE_LOCK:
        hit = _FUT_CACHE.get(cache_key)
        if hit and now - hit["ts"] < 45:
            return hit["data"]
    if source == "hyperliquid":
        report = fetch_hl_inst(symbol)
    elif fetch_futures is None:
        return None
    else:
        report = fetch_binance_inst(symbol)
    with _FUT_CACHE_LOCK:
        _FUT_CACHE[cache_key] = {"ts": now, "data": report}
    return report


def fetch_hl_inst(symbol):
    coin = SYMBOL_TO_HL.get(symbol)
    if coin is None:
        return None
    try:
        meta, ctxs = hl_post({"type": "metaAndAssetCtxs"})
        idx = next(i for i, u in enumerate(meta["universe"]) if u["name"] == coin)
        ctx = ctxs[idx]
        now_ms = int(time.time() * 1000)
        funding_rows = hl_post({
            "type": "fundingHistory", "coin": coin,
            "startTime": now_ms - 24 * 3_600_000, "endTime": now_ms,
        })
    except Exception:
        return None
    funding_rate = float(ctx.get("funding", 0))
    funding_hist = [float(r.get("fundingRate", 0)) for r in funding_rows[-24:]]
    oi = float(ctx.get("openInterest", 0))
    mark = float(ctx.get("markPx", 0))
    day_vol = float(ctx.get("dayNtlVlm", 0))

    parts = {
        "funding": score_funding(funding_rate, funding_hist),
        "oi": (0.0, f"Hyperliquid 持仓量 {oi:,.0f} USD"),
        "taker": (0.0, f"24h 名义成交 {day_vol/1e6:,.0f}M USD"),
        "ls": (0.0, "链上多空账户比暂未公开"),
        "top": (0.0, "大户持仓比暂未公开"),
    }
    weights = {"funding": 0.70, "oi": 0.10, "taker": 0.20,
               "ls": 0.0, "top": 0.0}
    total = sum(s * weights[k] for k, (s, _) in parts.items())
    total = max(-1.0, min(1.0, total))
    direction = "bullish" if total > 0.12 else ("bearish" if total < -0.12 else "neutral")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "source": "hyperliquid",
        "mark_price": mark,
        "funding_rate": funding_rate,
        "open_interest": oi,
        "taker_ratio": None,
        "long_short_ratio": None,
        "top_position_ratio": None,
        "score": round(total, 3),
        "direction": direction,
        "details": {k: {"score": round(s, 2), "note": note}
                    for k, (s, note) in parts.items()},
        "disclaimer": "基于 Hyperliquid 链上公开数据计算，仅反映资金结构，不构成投资建议。",
    }


def fetch_binance_inst(symbol):
    try:
        d = fetch_futures(symbol)
    except Exception:
        return None
    parts = {
        "funding": score_funding(d["funding_rate"], d["funding_history"]),
        "oi": score_oi(d["open_interest"], d["oi_history"], d["mark_price"]),
        "taker": score_taker(d["taker_history"]),
        "ls": score_ls(d["ls_history"], "多空账户比"),
        "top": score_ls(d["top_history"], "大户持仓比"),
    }
    weights = {"funding": 0.30, "oi": 0.15, "taker": 0.25, "ls": 0.15, "top": 0.15}
    total = sum(s * weights[k] for k, (s, _) in parts.items())
    total = max(-1.0, min(1.0, total))
    direction = "bullish" if total > 0.12 else ("bearish" if total < -0.12 else "neutral")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "source": "binance",
        "mark_price": d["mark_price"],
        "funding_rate": d["funding_rate"],
        "open_interest": d["open_interest"],
        "taker_ratio": d["taker_history"][-1] if d["taker_history"] else None,
        "long_short_ratio": d["ls_history"][-1] if d["ls_history"] else None,
        "top_position_ratio": d["top_history"][-1] if d["top_history"] else None,
        "score": round(total, 3),
        "direction": direction,
        "details": {k: {"score": round(s, 2), "note": note}
                    for k, (s, note) in parts.items()},
        "disclaimer": "基于公开合约数据的量化评分，仅反映资金结构，不构成投资建议。",
    }
    return report


def build_df(rows):
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    c = df["c"].astype(float)
    h = df["h"].astype(float)
    l = df["l"].astype(float)
    v = df["v"].astype(float)
    df["ma20"] = c.rolling(20).mean()
    df["ma50"] = c.rolling(50).mean()
    df["ema20"] = c.ewm(span=20, adjust=False).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - 100 / (1 + rs)
    e12 = c.ewm(span=12, adjust=False).mean()
    e26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = e12 - e26
    df["macd_sig"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]
    tr = pd.concat([(h - l).abs(), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()],
                   axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    mid = c.rolling(20).mean()
    std = c.rolling(20).std()
    df["bbu"] = mid + 2 * std
    df["bbl"] = mid - 2 * std
    df["vol_ma"] = v.rolling(20).mean()
    return df.reset_index(drop=True)


def find_swing_levels(df, window=5, tolerance_ratio=0.002):
    highs = df["h"].to_numpy()
    lows = df["l"].to_numpy()
    times = df["t"].to_numpy()
    pts = []
    n = len(df)
    for i in range(window, n - window):
        seg_h = highs[i - window:i + window + 1]
        seg_l = lows[i - window:i + window + 1]
        if highs[i] == seg_h.max():
            pts.append((times[i], "R", float(highs[i])))
        if lows[i] == seg_l.min():
            pts.append((times[i], "S", float(lows[i])))
    price = float(df["c"].iloc[-1])
    tol = price * tolerance_ratio
    clusters = []
    for ts, kind, val in pts:
        placed = False
        for cl in clusters:
            avg = sum(cl["values"]) / len(cl["values"])
            if abs(avg - val) <= tol:
                cl["values"].append(val)
                cl["count"] += 1
                placed = True
                break
        if not placed:
            clusters.append({"kind": kind, "values": [val], "count": 1,
                             "time": int(ts)})
    for cl in clusters:
        cl["value"] = float(np.mean(cl["values"]))
    supports = sorted([c for c in clusters if c["value"] < price],
                      key=lambda x: x["value"], reverse=True)
    resists = sorted([c for c in clusters if c["value"] > price],
                     key=lambda x: x["value"])
    return supports[:4], resists[:4]


def fib_levels(df):
    hi = float(df["h"].tail(120).max())
    lo = float(df["l"].tail(120).min())
    price = float(df["c"].iloc[-1])
    diff = hi - lo
    if diff <= 0:
        return []
    levels = []
    for ratio, label in [(0.236, "F0.236"), (0.382, "F0.382"),
                         (0.5, "F0.500"), (0.618, "F0.618"), (0.786, "F0.786")]:
        val = hi - diff * ratio
        levels.append({"value": round(val, 2), "label": label,
                       "kind": "S" if val < price else "R"})
    return levels


def cost_basis_nodes(df, buckets=24):
    tail = df.tail(200)
    lo = float(tail["l"].min())
    hi = float(tail["h"].max())
    price = float(df["c"].iloc[-1])
    if hi - lo <= 0:
        return [], []
    edges = np.linspace(lo, hi, buckets + 1)
    vols = np.zeros(buckets)
    mids = (tail["h"].to_numpy() + tail["l"].to_numpy()) / 2
    vols_arr = tail["v"].to_numpy()
    idx = np.clip(np.digitize(mids, edges) - 1, 0, buckets - 1)
    for i, b in enumerate(idx):
        vols[b] += vols_arr[i]
    centers = (edges[:-1] + edges[1:]) / 2
    nodes = []
    for i in range(buckets):
        if vols[i] > 0:
            nodes.append({"value": round(float(centers[i]), 2),
                          "volume": round(float(vols[i]), 2)})
    nodes.sort(key=lambda x: x["volume"], reverse=True)
    supports = sorted([n for n in nodes if n["value"] < price],
                      key=lambda x: x["value"], reverse=True)[:3]
    resists = sorted([n for n in nodes if n["value"] > price],
                     key=lambda x: x["value"])[:3]
    return supports, resists


def detect_patterns(df):
    n = len(df)
    if n < 60:
        return []
    pats = []
    last = df.iloc[-1]
    prev = df.iloc[-2]
    body = last["c"] - last["o"]
    rng = max(last["h"] - last["l"], 1e-9)
    prev_rng = max(prev["h"] - prev["l"], 1e-9)
    atr = float(last["atr"]) if not math.isnan(last["atr"]) else rng

    if body > 0 and prev["c"] < prev["o"] and last["o"] <= prev["c"] and last["c"] >= prev["o"]:
        pats.append({"time": int(last["t"]), "name": "看涨吞没",
                     "kind": "bull", "pos": "belowBar", "shape": "arrowUp"})
    if body < 0 and prev["c"] > prev["o"] and last["o"] >= prev["c"] and last["c"] <= prev["o"]:
        pats.append({"time": int(last["t"]), "name": "看跌吞没",
                     "kind": "bear", "pos": "aboveBar", "shape": "arrowDown"})

    upper_wick = last["h"] - max(last["o"], last["c"])
    lower_wick = min(last["o"], last["c"]) - last["l"]
    if abs(body) <= rng * 0.1:
        pats.append({"time": int(last["t"]), "name": "十字星",
                     "kind": "flat", "pos": "aboveBar", "shape": "circle"})
    if lower_wick >= abs(body) * 2 and upper_wick <= abs(body) * 0.6 and last["c"] > last["o"]:
        pats.append({"time": int(last["t"]), "name": "锤子线",
                     "kind": "bull", "pos": "belowBar", "shape": "arrowUp"})
    if upper_wick >= abs(body) * 2 and lower_wick <= abs(body) * 0.6 and last["c"] < last["o"]:
        pats.append({"time": int(last["t"]), "name": "射击之星",
                     "kind": "bear", "pos": "aboveBar", "shape": "arrowDown"})
    if last["h"] <= prev["h"] and last["l"] >= prev["l"]:
        pats.append({"time": int(last["t"]), "name": "内包线",
                     "kind": "flat", "pos": "aboveBar", "shape": "circle"})

    hi48 = float(df["h"].tail(50).iloc[:-1].max())
    lo48 = float(df["l"].tail(50).iloc[:-1].min())
    if last["c"] > hi48:
        pats.append({"time": int(last["t"]), "name": "向上突破",
                     "kind": "bull", "pos": "belowBar", "shape": "arrowUp"})
    elif last["c"] < lo48:
        pats.append({"time": int(last["t"]), "name": "向下突破",
                     "kind": "bear", "pos": "aboveBar", "shape": "arrowDown"})

    closes = df["c"].tail(6).to_numpy()
    if all(closes[i] > closes[i - 1] for i in range(1, len(closes))):
        pats.append({"time": int(last["t"]), "name": "连续走高",
                     "kind": "bull", "pos": "belowBar", "shape": "arrowUp"})
    elif all(closes[i] < closes[i - 1] for i in range(1, len(closes))):
        pats.append({"time": int(last["t"]), "name": "连续走低",
                     "kind": "bear", "pos": "aboveBar", "shape": "arrowDown"})

    x = np.arange(50, dtype=float)
    y = df["c"].tail(50).to_numpy()
    slope = float(np.polyfit(x, y, 1)[0]) / atr if atr else 0.0
    if slope > 0.15:
        pats.append({"time": int(last["t"]), "name": "上升趋势",
                     "kind": "bull", "pos": "belowBar", "shape": "arrowUp"})
    elif slope < -0.15:
        pats.append({"time": int(last["t"]), "name": "下降趋势",
                     "kind": "bear", "pos": "aboveBar", "shape": "arrowDown"})
    return pats[:6]


def trend_score(df):
    last = df.iloc[-1]
    price = float(last["c"])
    s = 0.0
    if not math.isnan(last["ma20"]):
        s += 0.25 if price > last["ma20"] else -0.25
    if not math.isnan(last["ma50"]):
        s += 0.25 if price > last["ma50"] else -0.25
    if not math.isnan(last["ema20"]):
        s += 0.15 if price > last["ema20"] else -0.15
    slope_50 = df["c"].tail(50)
    if len(slope_50) >= 10:
        slope = np.polyfit(np.arange(len(slope_50)), slope_50.to_numpy(), 1)[0]
        s += 0.2 if slope > 0 else -0.2
    return max(-1.0, min(1.0, s))


def rsi_score(v):
    if v is None or math.isnan(v):
        return 0.0
    if v >= 70:
        return -0.4
    if v <= 30:
        return 0.4
    return (v - 50) / 50


def macd_score(df):
    last = df.iloc[-1]
    if math.isnan(last["macd"]) or math.isnan(last["macd_hist"]):
        return 0.0
    s = 0.35 if last["macd"] > 0 else -0.35
    s += 0.15 if last["macd_hist"] > 0 else -0.15
    return s


def technical_score(df):
    last = df.iloc[-1]
    return max(-1.0, min(1.0, trend_score(df) * 0.4 +
                         rsi_score(last["rsi"]) * 0.25 +
                         macd_score(df) * 0.35))


def mtf_context(symbol, source="binance"):
    rows = []
    total = 0.0
    for tf, label in MTF_TIMEFRAMES:
        try:
            if source == "hyperliquid":
                klines = fetch_hl_klines(symbol, tf, limit=180)
            else:
                klines = fetch_klines(symbol, tf, limit=180)
            df = build_df(klines)
            last = df.iloc[-1]
            tech = technical_score(df)
            rsi_txt = "—" if math.isnan(last["rsi"]) else f"{last['rsi']:.1f}"
            direction = "long" if tech > 0.15 else ("short" if tech < -0.15 else "neutral")
            dir_cn = {"long": "偏多", "short": "偏空", "neutral": "震荡"}[direction]
            macd_txt = "多头" if last["macd"] > 0 else "空头"
            total += tech
            rows.append({
                "tf": label, "trend": dir_cn, "rsi": rsi_txt,
                "macd": macd_txt, "price": round(float(last["c"]), 2),
                "score": round(tech, 2),
            })
        except Exception as e:
            rows.append({"tf": label, "trend": "无数据", "rsi": "—",
                         "macd": "—", "price": 0, "score": 0,
                         "err": str(e)[:60]})
    return rows, max(-1.0, min(1.0, total / max(len(rows), 1)))


def build_plan(df, mtf_rows, mtf_score, inst):
    last = df.iloc[-1]
    price = float(last["c"])
    atr = float(last["atr"]) if not math.isnan(last["atr"]) else price * 0.01
    atr_pct = atr / price * 100 if price else 0
    tech = technical_score(df)
    inst_score = float(inst.get("score", 0.0)) if inst else 0.0
    total = 0.35 * mtf_score + 0.35 * tech + 0.30 * inst_score
    total = max(-1.0, min(1.0, total))

    direction = "long" if total > 0.12 else ("short" if total < -0.12 else "neutral")
    dir_cn = {"long": "看多", "short": "看空", "neutral": "观望"}[direction]
    confidence = int(max(38, min(95, 50 + abs(total) * 42)))
    rr = 1.8

    supports, resists = find_swing_levels(df)
    patterns = detect_patterns(df)
    bullish_pat = any(p["kind"] == "bull" for p in patterns)
    bearish_pat = any(p["kind"] == "bear" for p in patterns)

    if direction == "long":
        entry = price
        if bullish_pat:
            trigger = "突破或形态确认后顺势做多"
        elif resists:
            trigger = f"回踩关键支撑后做多，上方阻力确认 {resists[0]['value']:,.2f}"
        else:
            trigger = "顺势做多，回踩均线加仓"
        sl = price - atr * 1.5
        tp = price + (price - sl) * rr
    elif direction == "short":
        entry = price
        if bearish_pat:
            trigger = "跌破或形态确认后顺势做空"
        elif supports:
            trigger = f"反弹至关键阻力后做空，下方支撑参考 {supports[0]['value']:,.2f}"
        else:
            trigger = "顺势做空，反弹均线加仓"
        sl = price + atr * 1.5
        tp = price - (sl - price) * rr
    else:
        entry = price
        trigger = "等待方向确认：突破上方阻力做多 / 跌破下方支撑做空"
        sl = price - atr * 1.2
        tp = price + atr * 1.5

    reasons = []
    if mtf_rows:
        longs = sum(1 for r in mtf_rows if r.get("trend") == "偏多")
        shorts = sum(1 for r in mtf_rows if r.get("trend") == "偏空")
        if longs > shorts:
            reasons.append(f"多周期结构偏多 ({longs}/{len(mtf_rows)} 周期看多)")
        elif shorts > longs:
            reasons.append(f"多周期结构偏空 ({shorts}/{len(mtf_rows)} 周期看空)")
        else:
            reasons.append("多周期结构分化，方向有待确认")
    if not math.isnan(last["rsi"]):
        if last["rsi"] >= 70:
            reasons.append(f"RSI {last['rsi']:.1f} 进入超买区，追多风险高")
        elif last["rsi"] <= 30:
            reasons.append(f"RSI {last['rsi']:.1f} 进入超卖区，留意反弹")
        else:
            reasons.append(f"RSI {last['rsi']:.1f} 处于中性区间")
    if not math.isnan(last["macd"]):
        macd_state = "多头" if last["macd"] > 0 else "空头"
        hist_state = "动能增强" if last["macd_hist"] > 0 else "动能转弱"
        reasons.append(f"MACD {macd_state} · {hist_state}")
    if inst:
        inst_dir = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}.get(
            inst.get("direction"), "中性")
        reasons.append(f"合约资金面 {inst_dir} (评分 {inst.get('score', 0):+.2f})")
    for p in patterns[:2]:
        reasons.append(f"识别到形态：{p['name']}")
    reasons.append(f"止损参考 {sl:,.2f}，止盈参考 {tp:,.2f}，盈亏比约 1:{rr}")
    reasons = reasons[:7]

    return {
        "direction": direction,
        "direction_cn": dir_cn,
        "confidence": confidence,
        "entry": round(entry, 2),
        "trigger": trigger,
        "sl": round(sl, 2),
        "tp": round(tp, 2),
        "risk": round(abs(sl - entry) / entry * 100, 2) if entry else 0,
        "reward": round(abs(tp - entry) / entry * 100, 2) if entry else 0,
        "rr": rr,
        "atr_pct": round(atr_pct, 2),
        "reasons": reasons,
        "score": round(total, 2),
    }


def round_or_none(v, nd=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(float(v), nd)


def build_snapshot(symbol, interval, source="binance"):
    if source == "hyperliquid":
        klines = fetch_hl_klines(symbol, interval, limit=500)
    else:
        klines = fetch_klines(symbol, interval, limit=500)
    df = build_df(klines)
    last = df.iloc[-1]
    price = float(last["c"])
    prev = float(df["c"].iloc[-2]) if len(df) > 1 else price
    chg = (price - prev) / prev * 100 if prev else 0
    supports, resists = find_swing_levels(df)
    fibs = fib_levels(df)
    cbd_s, cbd_r = cost_basis_nodes(df)
    patterns = detect_patterns(df)
    mtf_rows, mtf_score = mtf_context(symbol, source)
    inst = fetch_inst(symbol, source)
    plan = build_plan(df, mtf_rows, mtf_score, inst)
    vol_ratio = float(last["v"] / last["vol_ma"]) if not math.isnan(last["vol_ma"]) and last["vol_ma"] > 0 else 0
    atr_pct = float(last["atr"]) / price * 100 if price and not math.isnan(last["atr"]) else 0

    tail = df.tail(300)
    series_ma20 = [{"time": int(r["t"]), "value": round_or_none(r["ma20"])}
                   for _, r in tail.iterrows() if not math.isnan(r["ma20"])]
    series_ma50 = [{"time": int(r["t"]), "value": round_or_none(r["ma50"])}
                   for _, r in tail.iterrows() if not math.isnan(r["ma50"])]
    series_ema20 = [{"time": int(r["t"]), "value": round_or_none(r["ema20"])}
                    for _, r in tail.iterrows() if not math.isnan(r["ema20"])]
    series_bbu = [{"time": int(r["t"]), "value": round_or_none(r["bbu"])}
                  for _, r in tail.iterrows() if not math.isnan(r["bbu"])]
    series_bbl = [{"time": int(r["t"]), "value": round_or_none(r["bbl"])}
                  for _, r in tail.iterrows() if not math.isnan(r["bbl"])]
    series_rsi = [{"time": int(r["t"]), "value": round_or_none(r["rsi"])}
                  for _, r in tail.iterrows() if not math.isnan(r["rsi"])]
    series_macd = [{"time": int(r["t"]), "value": round_or_none(r["macd"])}
                   for _, r in tail.iterrows() if not math.isnan(r["macd"])]
    series_macd_sig = [{"time": int(r["t"]), "value": round_or_none(r["macd_sig"])}
                       for _, r in tail.iterrows() if not math.isnan(r["macd_sig"])]
    series_macd_hist = [{"time": int(r["t"]), "value": round_or_none(r["macd_hist"])}
                        for _, r in tail.iterrows() if not math.isnan(r["macd_hist"])]

    price_lines = []
    for i, s in enumerate(resists[:3]):
        price_lines.append({"price": s["value"], "kind": "R", "title": f"R{i+1}",
                            "color": "#f6465d"})
    for i, s in enumerate(supports[:3]):
        price_lines.append({"price": s["value"], "kind": "S", "title": f"S{i+1}",
                            "color": "#26d07c"})
    for f in fibs[:3]:
        price_lines.append({"price": f["value"], "kind": "F", "title": f["label"],
                            "color": "#f0b90b"})
    for n in cbd_r[:2]:
        price_lines.append({"price": n["value"], "kind": "CBD", "title": "筹码",
                            "color": "#a371f7"})
    for n in cbd_s[:2]:
        price_lines.append({"price": n["value"], "kind": "CBD", "title": "筹码",
                            "color": "#a371f7"})
    price_lines.sort(key=lambda x: x["price"])
    price_lines = price_lines[:10]

    intervals = dict((t, (label, secs)) for t, label, secs in TIMEFRAMES)
    label, refresh = intervals.get(interval, (interval, 120))

    indicators = [
        {"name": "MA20", "value": round_or_none(last["ma20"]),
         "judge": "价格上方" if price >= last["ma20"] else "价格下方"},
        {"name": "MA50", "value": round_or_none(last["ma50"]),
         "judge": "价格上方" if price >= last["ma50"] else "价格下方"},
        {"name": "EMA20", "value": round_or_none(last["ema20"]),
         "judge": "价格上方" if price >= last["ema20"] else "价格下方"},
        {"name": "RSI(14)", "value": round_or_none(last["rsi"], 1),
         "judge": "超买" if last["rsi"] >= 70 else "超卖" if last["rsi"] <= 30 else "中性"},
        {"name": "MACD", "value": round_or_none(last["macd"], 1),
         "judge": "多头" if last["macd"] > 0 else "空头"},
        {"name": "MACD 柱", "value": round_or_none(last["macd_hist"], 1),
         "judge": "动能增强" if last["macd_hist"] > 0 else "动能转弱"},
        {"name": "ATR(14)", "value": round_or_none(last["atr"]),
         "judge": f"波动 {atr_pct:.2f}%"},
        {"name": "量能比", "value": round(vol_ratio, 2),
         "judge": "放量" if vol_ratio > 1.5 else "缩量" if vol_ratio < 0.6 else "正常"},
    ]

    levels = []
    levels.append({"type": "上方阻力", "price": resists[0]["value"] if resists else price * 1.02,
                   "note": "摆动高点/筹码密集区"})
    levels.append({"type": "下方支撑", "price": supports[0]["value"] if supports else price * 0.98,
                   "note": "摆动低点/筹码密集区"})
    hi96 = float(df["h"].tail(96).max())
    lo96 = float(df["l"].tail(96).min())
    levels.append({"type": "近96根高点", "price": hi96, "note": "区间上沿"})
    levels.append({"type": "近96根低点", "price": lo96, "note": "区间下沿"})
    for f in fibs[:2]:
        levels.append({"type": f["label"], "price": f["value"], "note": "斐波那契回撤"})

    kline_payload = [{"t": int(r["t"]), "o": float(r["o"]), "h": float(r["h"]),
                      "l": float(r["l"]), "c": float(r["c"]), "v": float(r["v"])}
                     for _, r in df.tail(400).iterrows()]

    return {
        "source": source,
        "source_cn": "币安" if source == "binance" else "Hyperliquid",
        "symbol": symbol,
        "symbol_cn": dict(SYMBOLS).get(symbol, symbol),
        "interval": interval,
        "interval_cn": label,
        "refresh": refresh,
        "price": round(price, 2),
        "chg": round(chg, 2),
        "updated": now_cn(),
        "atr_pct": round(atr_pct, 2),
        "volume_ratio": round(vol_ratio, 2),
        "klines": kline_payload,
        "series": {
            "ma20": series_ma20, "ma50": series_ma50, "ema20": series_ema20,
            "bbu": series_bbu, "bbl": series_bbl,
            "rsi": series_rsi, "macd": series_macd,
            "macd_sig": series_macd_sig, "macd_hist": series_macd_hist,
        },
        "supports": [{"price": s["value"], "count": s["count"]} for s in supports[:3]],
        "resists": [{"price": s["value"], "count": s["count"]} for s in resists[:3]],
        "fibs": fibs[:3],
        "cbd_s": cbd_s, "cbd_r": cbd_r,
        "patterns": patterns,
        "price_lines": price_lines,
        "plan": plan,
        "inst": inst,
        "mtf": mtf_rows,
        "indicators": indicators,
        "levels": levels,
        "disclaimer": "全部指标基于币安公开合约行情实时计算，历史与预测均不构成投资建议。",
    }


def load_template():
    path = os.path.join(HERE, "analysis_template.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


def render_analysis(symbol, interval, source, template):
    try:
        snap = build_snapshot(symbol, interval, source)
    except Exception as e:
        snap = {"error": f"{type(e).__name__}: {e}", "updated": now_cn(),
                "source": source,
                "source_cn": "币安" if source == "binance" else "Hyperliquid",
                "symbol": symbol, "interval": interval, "interval_cn": interval,
                "refresh": 30, "price": 0, "chg": 0, "klines": [],
                "series": {}, "supports": [], "resists": [], "fibs": [],
                "cbd_s": [], "cbd_r": [], "patterns": [], "price_lines": [],
                "plan": {"direction": "neutral", "direction_cn": "无数据",
                         "confidence": 0, "entry": 0, "trigger": "行情拉取失败",
                         "sl": 0, "tp": 0, "risk": 0, "reward": 0, "rr": 1,
                         "atr_pct": 0, "reasons": [str(e)], "score": 0},
                "inst": None, "mtf": [], "indicators": [], "levels": [],
                "disclaimer": "行情拉取失败。"}
    data_json = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
    html = template.replace("__DATA_JSON__", data_json)
    html = html.replace("__REFRESH__", str(snap.get("refresh", 120)))
    html = html.replace("__NAV__", NAV)
    return html


NAV = """
<nav class="topbar">
  <div class="topbar-left">
    <a class="brand" href="/index.html">Kairo Hub</a>
    <span class="brand-sub">真实数据 · 公开可验证</span>
  </div>
  <div class="topbar-links">
    <a href="/index.html">总览</a>
    <a href="/analysis.html" class="active">实时分析</a>
    <a href="/ledger.html">信号账本</a>
    <a href="/verify.html">手机验证</a>
  </div>
</nav>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "KairoHub/1.0"

    def log_message(self, fmt, *args):
        print(f"[{now_cn()}] {self.address_string()} {fmt % args}")

    def _send(self, code, body, ctype="text/html; charset=utf-8", headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code, data):
        self._send(code, json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                   ctype="application/json; charset=utf-8")

    def stream_verify_events(self, req_id):
        session = VERIFY_SESSIONS.get(req_id)
        if not session:
            self._send(404, "not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = queue.Queue()
        with VERIFY_LOCK:
            session["listeners"].append(q)
        try:
            for ev in list(session["events"]):
                payload = json.dumps(ev, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            deadline = time.time() + 25
            while time.time() < deadline:
                try:
                    ev = q.get(timeout=1)
                except queue.Empty:
                    continue
                payload = json.dumps(ev, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                if ev.get("stage") in ("sent", "verified", "failed"):
                    break
        finally:
            with VERIFY_LOCK:
                if q in session.get("listeners", []):
                    session["listeners"].remove(q)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path == "/api/verify/events":
            self.stream_verify_events((qs.get("req") or [""])[0])
            return
        if path in ("/", "/index.html"):
            self._serve_file("index.html")
            return
        if path in ("/verify", "/verify.html"):
            self._serve_file("verify.html")
            return
        if path in ("/analysis", "/analysis.html"):
            symbol = (qs.get("symbol") or ["BTCUSDT"])[0].upper()
            interval = (qs.get("interval") or ["1h"])[0].lower()
            source = (qs.get("source") or ["binance"])[0].lower()
            if symbol not in dict(SYMBOLS):
                symbol = "BTCUSDT"
            if interval not in dict((t, 1) for t, _, _ in TIMEFRAMES):
                interval = "1h"
            if source not in SOURCES:
                source = "binance"
            self._send(200, render_analysis(symbol, interval, source, TEMPLATE))
            return
        if path == "/ledger.html":
            self._serve_file("ledger.html")
            return
        if path.startswith("/assets/"):
            rel = path.lstrip("/")
            fp = os.path.join(HERE, rel)
            if os.path.isfile(fp):
                ctype = "application/javascript" if fp.endswith(".js") else "application/octet-stream"
                with open(fp, "rb") as f:
                    self._send(200, f.read(), ctype=ctype,
                               headers={"Cache-Control": "max-age=3600"})
            else:
                self._send(404, "not found")
            return
        if path == "/favicon.ico":
            self._send(404, "")
            return
        self._send(404, "not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._send_json(400, {"ok": False, "error": "请求格式错误"})
            return

        if path == "/api/verify/send":
            phone = str(body.get("phone", "")).strip()
            if not valid_phone(phone):
                self._send_json(400, {"ok": False, "error": "请输入正确的 11 位手机号"})
                return
            now = time.time()
            with VERIFY_LOCK:
                last = VERIFY_RATE.get(phone, 0)
                if now - last < SEND_INTERVAL:
                    wait = int(SEND_INTERVAL - (now - last))
                    self._send_json(429, {"ok": False,
                                          "error": f"发送过于频繁，请 {wait} 秒后重试",
                                          "retry_after": wait})
                    return
                VERIFY_RATE[phone] = now
            req_id, session = new_verify_session(phone)
            threading.Thread(target=send_code_progress,
                             args=(req_id, phone), daemon=True).start()
            self._send_json(200, {
                "ok": True,
                "request_id": req_id,
                "phone_masked": mask_phone(phone),
                "demo": True,
                "demo_code": session["code"],
                "expires_in": CODE_TTL,
            })
            return

        if path == "/api/verify/check":
            phone = str(body.get("phone", "")).strip()
            code = str(body.get("code", "")).strip()
            req_id = str(body.get("request_id", "")).strip()
            session = VERIFY_SESSIONS.get(req_id)
            if not session or session["phone"] != phone:
                self._send_json(400, {"ok": False, "error": "验证会话不存在，请重新获取验证码"})
                return
            if session["status"] == "verified":
                self._send_json(200, {"ok": True, "phone_masked": mask_phone(phone),
                                      "next": "/analysis.html"})
                return
            if time.time() > session["expires"]:
                add_verify_event(session, "failed", "验证码已过期，请重新获取")
                self._send_json(400, {"ok": False, "error": "验证码已过期，请重新获取"})
                return
            if code != session["code"]:
                session["attempts"] += 1
                remaining = MAX_ATTEMPTS - session["attempts"]
                if remaining <= 0:
                    add_verify_event(session, "failed", "错误次数过多，会话已锁定")
                    self._send_json(400, {"ok": False, "error": "错误次数过多，请重新获取验证码"})
                else:
                    self._send_json(400, {"ok": False,
                                          "error": f"验证码错误，还可尝试 {remaining} 次"})
                return
            session["status"] = "verified"
            add_verify_event(session, "verified", "验证通过，正在进入实时终端")
            self._send_json(200, {"ok": True, "phone_masked": mask_phone(phone),
                                  "next": "/analysis.html"})
            return

        self._send_json(404, {"ok": False, "error": "接口不存在"})

    def _serve_file(self, name):
        fp = os.path.join(HERE, name)
        if not os.path.isfile(fp):
            self._send(404, "not found")
            return
        with open(fp, "rb") as f:
            self._send(200, f.read())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Kairo Hub 服务已启动: http://{args.host}:{args.port}/analysis.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


TEMPLATE = load_template()

if __name__ == "__main__":
    main()

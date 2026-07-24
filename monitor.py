#!/usr/bin/env python3
"""ETH/USDT 实时监控 — 每 1h 自动拉数据出预测, 输出到日志"""
import sys, os, time, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

from predict import (fetch_data, calc_indicators, signal_technical,
                     signal_ml, signal_onchain, signal_sentiment,
                     signal_orderbook, find_support_resistance)

LOG_FILE = "monitor_log.csv"
INTERVAL = 3600  # 1小时

def run_prediction():
    """执行一次完整预测"""
    result = {"time": datetime.now().isoformat()}
    
    try:
        df = fetch_data(80, "1h")
        df = calc_indicators(df)
        row = df.iloc[-1]
        result["price"] = round(row["close"], 2)
        result["timestamp"] = str(df.index[-1])
        
        # 技术面
        tech = signal_technical(df)
        ts = sum(s*w for s,w,_ in tech) / sum(w for _,w,_ in tech) if tech else 0
        result["tech_score"] = round(ts, 3)
        
        # ML
        ml = signal_ml(df, 2)
        ml_score = ml.get("score", 0)
        result["ml_score"] = round(ml_score, 3)
        result["ml_detail"] = ml.get("detail", "N/A")
        
        # 盘口
        ob = signal_orderbook()
        ob_score = ob.get("score", 0)
        result["ob_score"] = round(ob_score, 3)
        result["ob_detail"] = ob.get("detail", "N/A")
        
        # 链上
        on = signal_onchain()
        result["onchain"] = on.get("detail", "N/A")
        
        # 情绪
        sent = signal_sentiment()
        result["sentiment"] = sent.get("detail", "N/A")
        
        # 综合
        total_score = ts * 0.5 + ml_score * 0.25 + ob_score * 0.15
        result["total_score"] = round(total_score, 3)
        
        # 方向
        if total_score > 0.2:
            result["direction"] = "LONG"
        elif total_score < -0.2:
            result["direction"] = "SHORT"
        else:
            result["direction"] = "NEUTRAL"
        
        # 支撑阻力
        supports, resistances = find_support_resistance(df.tail(48))
        near_s = min([p for p,_ in supports if p < row["close"]], default=None)
        near_r = min([p for p,_ in resistances if p > row["close"]], default=None)
        result["support"] = round(near_s, 0) if near_s else None
        result["resistance"] = round(near_r, 0) if near_r else None
        
        result["status"] = "OK"
    except Exception as e:
        result["status"] = f"ERROR: {e}"
    
    return result

def log_result(r):
    """写日志"""
    header = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a") as f:
        if header:
            f.write("time,price,score,direction,support,resistance,status\n")
        line = f"{r['time']},{r.get('price','')},{r.get('total_score','')},"
        line += f"{r.get('direction','')},{r.get('support','')},{r.get('resistance','')},{r.get('status','')}\n"
        f.write(line)

if __name__ == "__main__":
    print(f"\n  ETH/USDT 实时监控启动")
    print(f"  每 {INTERVAL//3600}h 执行一次, 日志写入 {LOG_FILE}\n")
    
    run_num = 1
    while True:
        print(f"[{run_num}] {datetime.now().strftime('%Y-%m-%d %H:%M')} 正在预测...")
        r = run_prediction()
        log_result(r)
        
        price = r.get("price", "?")
        score = r.get("total_score", "?")
        direction = r.get("direction", "?")
        sup = r.get("support", "-")
        res = r.get("resistance", "-")
        
        dir_sym = {"LONG": "📈 看涨", "SHORT": "📉 看跌", "NEUTRAL": "➖ 震荡"}
        
        print(f"    价格: ${price}  |  评分: {score}  |  {dir_sym.get(direction, direction)}")
        print(f"    支撑: ${sup}  阻力: ${res}")
        print(f"    等待 {INTERVAL//3600} 小时...\n")
        
        run_num += 1
        if run_num > 100:  # 安全上限
            break
        time.sleep(INTERVAL)

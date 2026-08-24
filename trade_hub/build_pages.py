#!/usr/bin/env python3
"""生成三页产品：总览(index) / 实时分析(analysis) / 信号账本(ledger)。"""

import json, os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_signals():
    path = os.path.join(HERE, "signals.jsonl")
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return rows


NAV = """
<nav class="nav">
  <a class="brand" href="/index.html">Kairo Hub</a>
  <div class="nav-links">
    <a href="/index.html" class="active">总览</a>
    <a href="/analysis.html">实时分析</a>
    <a href="/ledger.html">信号账本</a>
  </div>
</nav>
"""

CSS = """
<style>
  :root {
    --bg:#0d1117; --panel:#161b22; --line:#30363d; --txt:#e6edf3;
    --muted:#8b949e; --green:#3fb950; --red:#f85149; --amber:#d29922; --accent:#58a6ff;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--txt); font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; padding:24px; }
  .wrap { max-width:1100px; margin:0 auto; }
  .nav { display:flex; justify-content:space-between; align-items:center; background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:10px 18px; margin-bottom:20px; }
  .brand { font-weight:700; color:var(--txt); text-decoration:none; font-size:17px; }
  .nav-links { display:flex; gap:6px; }
  .nav-links a { color:var(--muted); text-decoration:none; padding:6px 14px; border-radius:6px; font-size:13px; }
  .nav-links a:hover { color:var(--txt); background:#1c2129; }
  .nav-links a.active { color:#fff; background:#21262d; }
  header { display:flex; justify-content:space-between; align-items:flex-end; border-bottom:1px solid var(--line); padding-bottom:14px; margin-bottom:20px; }
  h1 { font-size:22px; font-weight:700; }
  .sub { color:var(--muted); font-size:12px; margin-top:5px; }
  .disclaimer { color:var(--muted); font-size:11px; max-width:500px; text-align:right; line-height:1.6; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-bottom:20px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px 16px; }
  .card .k { color:var(--muted); font-size:11px; }
  .card .v { font-size:20px; font-weight:700; margin-top:5px; font-variant-numeric:tabular-nums; }
  .card .d { font-size:12px; margin-top:3px; }
  .up { color:var(--green); } .down { color:var(--red); } .flat { color:var(--muted); }
  .badge { display:inline-block; padding:3px 12px; border-radius:99px; font-size:13px; font-weight:600; }
  .badge.bull { background:rgba(63,185,80,.15); color:var(--green); }
  .badge.bear { background:rgba(248,81,73,.15); color:var(--red); }
  .badge.neutral { background:rgba(139,148,158,.15); color:var(--muted); }
  h2 { font-size:15px; margin:22px 0 10px; }
  table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; font-size:13px; }
  th,td { padding:9px 12px; text-align:left; border-bottom:1px solid var(--line); }
  th { background:#1c2129; color:var(--muted); font-weight:600; }
  tr:last-child td { border-bottom:none; }
  .pill { display:inline-block; padding:2px 10px; border-radius:99px; font-size:12px; }
  .pill.win { background:rgba(63,185,80,.12); color:var(--green); }
  .pill.loss { background:rgba(248,81,73,.12); color:var(--red); }
  .pill.open { background:rgba(210,153,34,.12); color:var(--amber); }
  .inst-rows { margin-top:12px; }
  .inst-row { display:flex; justify-content:space-between; padding:7px 2px; border-bottom:1px dashed var(--line); font-size:13px; }
  .inst-row:last-child { border-bottom:none; }
  .inst-row .d { color:var(--muted); }
  .pos { color:var(--green); } .neg { color:var(--red); }
  .note { color:var(--muted); font-size:11px; margin-top:18px; line-height:1.7; }
  .live { color:var(--green); font-size:11px; }
  .bar { height:8px; border-radius:4px; background:#21262d; margin-top:6px; overflow:hidden; }
  .bar > i { display:block; height:100%; border-radius:4px; }
  .bar.bull > i { background:var(--green); }
  .bar.bear > i { background:var(--red); }
  .bar.neutral > i { background:var(--amber); }
</style>
"""


def index_page(report, signals, inst):
    rows = signals[-12:]
    rows_html = ""
    if rows:
        for r in reversed(rows):
            cls = "win" if r.get("outcome") == "win" else "loss" if r.get("outcome") == "loss" else "open"
            txt = "盈利" if r.get("outcome") == "win" else "亏损" if r.get("outcome") == "loss" else "进行中"
            exit_px = r.get("exit_price")
            exit_txt = "—" if exit_px is None else f"{exit_px:,.0f}"
            rows_html += (
                f"<tr><td>{r['id']}</td><td>{'多' if r['direction']=='long' else '空'}</td>"
                f"<td>{r['symbol']}</td><td>{r['timeframe']}</td>"
                f"<td>{r['entry']:,.0f}</td><td>{r['sl']:,.0f}</td><td>{r['tp']:,.0f}</td>"
                f"<td><span class='pill {cls}'>{txt}</span></td>"
                f"<td>{exit_txt}</td>"
                f"<td>{r.get('published_at','')[:16]}</td></tr>"
            )
    else:
        rows_html = "<tr><td colspan='10'>暂无已发布信号</td></tr>"

    strats_html = ""
    for name, s in (report.get("strategies") or {}).items():
        m = s.get("metrics") or {}
        def fmt(v, s="", d=2):
            return "—" if v is None else f"{v:,.{d}f}{s}"
        strats_html += (
            f"<tr><td>{name}</td><td>{fmt(m.get('总收益%'),'%')}</td>"
            f"<td>{fmt(m.get('年化%'),'%')}</td><td>{fmt(m.get('最大回撤%'),'%')}</td>"
            f"<td>{fmt(m.get('胜率%'),'%')}</td><td>{fmt(m.get('盈亏比'))}</td>"
            f"<td>{fmt(m.get('夏普'))}</td><td>{fmt(m.get('交易次数'),'',0)}</td></tr>"
        )

    inst_head = ""
    if inst:
        dir_map = {"bullish": ("看多", "bull"), "bearish": ("看空", "bear"), "neutral": ("中性", "neutral")}
        dir_cn, cls = dir_map.get(inst.get("direction"), ("未知", "neutral"))
        score = inst.get("score")
        details = ""
        detail_map = {"funding": "资金费率", "oi": "持仓量变化", "taker": "主动买卖量", "ls": "多空账户", "top": "大户持仓"}
        for k, v in (inst.get("details") or {}).items():
            c = "pos" if v.get("score", 0) > 0 else "neg" if v.get("score", 0) < 0 else ""
            details += f"<div class='inst-row'><span>{detail_map.get(k, k)}</span><span class='{c}'>{v.get('score', 0):+.2f} · {v.get('note', '')}</span></div>"
        inst_head = f"""
        <div class="card" style="grid-column:1/-1">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div><span style="font-size:17px;font-weight:700">真实机构信号</span>
            <span class="badge {cls}">{dir_cn} · {score:+.2f}</span></div>
            <span class="sub">{inst.get('symbol','—')} · {(inst.get('generated_at') or '')[:19].replace('T',' ')}</span>
          </div>
          <div class="grid" style="margin-bottom:6px">
            <div class="card" style="padding:10px"><div class="k">标记价格</div><div class="v">${inst.get('mark_price',0):,.0f}</div></div>
            <div class="card" style="padding:10px"><div class="k">资金费率</div><div class="v">{inst.get('funding_rate',0)*100:.3f}%</div></div>
            <div class="card" style="padding:10px"><div class="k">持仓量</div><div class="v">{inst.get('open_interest',0):,.0f} BTC</div></div>
            <div class="card" style="padding:10px"><div class="k">主动买/卖</div><div class="v">{inst.get('taker_ratio',0):.2f}</div></div>
            <div class="card" style="padding:10px"><div class="k">多空账户比</div><div class="v">{inst.get('long_short_ratio',0):.2f}</div></div>
            <div class="card" style="padding:10px"><div class="k">大户持仓比</div><div class="v">{inst.get('top_position_ratio',0):.2f}</div></div>
          </div>
          <div class="inst-rows">{details}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kairo Hub · 总览</title>{CSS}</head><body><div class="wrap">
{NAV}
<header><div><h1>透明战绩中心</h1><div class="sub">{report.get('asset','—')} · {report.get('start','')} → {report.get('end','')} · {report.get('bars',0):,} 根K线</div></div>
<div class="disclaimer">{report.get('disclaimer','')}</div></header>
<div class="grid">{inst_head}</div>
<h2>策略回测（真实历史数据）</h2>
<table><tr><th>策略</th><th>总收益</th><th>年化</th><th>最大回撤</th><th>胜率</th><th>盈亏比</th><th>夏普</th><th>交易数</th></tr>{strats_html}</table>
<h2>最近信号</h2>
<table><tr><th>ID</th><th>方向</th><th>标的</th><th>周期</th><th>入场</th><th>止损</th><th>止盈</th><th>状态</th><th>出场价</th><th>发布时间</th></tr>{rows_html}</table>
<p class="note">免责声明：回测与信号统计均基于历史真实行情，未做前视偏差处理；历史表现不保证未来收益，本页面不构成投资建议。</p>
</div></body></html>"""


def analysis_page(inst):
    """服务端计算指标快照并直接嵌入页面，不依赖浏览器联网。"""
    import pandas as pd, numpy as np, json as _json

    csv_path = os.path.join(HERE, "btc_usdt_1h_2y.csv")
    snap = {}
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, parse_dates=["ts"]).sort_values("ts").reset_index(drop=True)
            c = df["close"].astype(float)
            last = float(c.iloc[-1]); prev = float(c.iloc[-2])
            ma20 = float(c.rolling(20).mean().iloc[-1])
            ma50 = float(c.rolling(50).mean().iloc[-1])
            delta = c.diff()
            gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            rsi = float((100 - 100/(1+rs)).iloc[-1])
            e12 = c.ewm(span=12, adjust=False).mean()
            e26 = c.ewm(span=26, adjust=False).mean()
            macd = e12 - e26
            sig = macd.ewm(span=9, adjust=False).mean()
            macdNow = float(macd.iloc[-1]); histNow = float((macd - sig).iloc[-1])
            tr = pd.concat([(df["high"]-df["low"]).abs(), (df["high"]-c.shift(1)).abs(), (df["low"]-c.shift(1)).abs()], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1]); atrPct = atr/last*100
            hi96 = float(df["high"].tail(96).max()); lo96 = float(df["low"].tail(96).min())
            chg = (last - prev) / prev * 100
            snap = {
                "symbol": "BTCUSDT", "price": round(last,2), "chg": round(chg,2),
                "ma20": round(ma20,2), "ma50": round(ma50,2), "rsi": round(rsi,1),
                "macd": round(macdNow,1), "macdHist": round(histNow,1), "atrPct": round(atrPct,2),
                "hi": round(hi96,2), "lo": round(lo96,2), "fib382": round(last-(hi96-lo96)*0.382,2),
                "trend": (("上行" if last>ma50 else "偏多") if last>ma20 else (("下行" if last<ma50 else "偏空"))),
                "updated": pd.Timestamp.now(tz="Asia/Shanghai").strftime("%Y-%m-%d %H:%M")
            }
        except Exception as e:
            snap = {"error": str(e), "updated": ""}

    analysis_json = _json.dumps(snap, ensure_ascii=False)
    inst_json = _json.dumps(inst, ensure_ascii=False)

    page = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kairo Hub · 实时分析</title>{CSS}</head><body><div class="wrap">
{NAV}
<header><div><h1>实时分析</h1><div class="sub" id="meta">数据更新于 __UPDATED__</div></div>
<div class="disclaimer">指标由本地服务基于币安公开 K 线计算并嵌入页面；运行 refresh.py 可刷新数据。</div></header>
<div class="grid" id="cards"></div>
<div class="grid"><div class="card" style="grid-column:1/-1" id="inst"></div></div>
<h2>技术指标（1h）</h2>
<table id="ind"></table>
<h2>关键价位</h2>
<table id="levels"></table>
<p class="note">免责声明：指标基于历史真实行情计算，仅供信息参考，不构成投资建议。</p>
</div>
<script>
const ANALYSIS = __ANALYSIS__;
const INST = __INST__;
function fmt(n, d=2) { return (n==null||!isFinite(n)) ? "—" : Number(n).toLocaleString("en-US",{maximumFractionDigits:d,minimumFractionDigits:d}); }
function render() {
  const A = ANALYSIS;
  document.getElementById("meta").textContent = "BTCUSDT · 1小时 · 数据更新于 " + (A.updated || "—");
  const chg = A.chg || 0;
  const rNow = A.rsi || 50;
  const histNow = A.macdHist || 0;
  document.getElementById("cards").innerHTML = `
    <div class="card"><div class="k">BTC/USDT</div><div class="v">${fmt(A.price,0)}</div><div class="${chg>=0?"up":"down"}">${chg>=0?"+":""}${fmt(chg,2)}%</div></div>
    <div class="card"><div class="k">趋势 (MA20/50)</div><div class="v">${A.trend||"—"}</div></div>
    <div class="card"><div class="k">RSI(14)</div><div class="v">${fmt(rNow,1)}</div><div class="bar ${rNow>=70?"bear":rNow<=30?"bull":"neutral"}"><i style="width:${Math.min(100,Math.max(4,rNow))}%"></i></div></div>
    <div class="card"><div class="k">MACD 柱</div><div class="v ${histNow>=0?"up":"down"}">${fmt(histNow,1)}</div></div>
    <div class="card"><div class="k">ATR (波动率)</div><div class="v">${fmt(A.atrPct,2)}%</div></div>
    <div class="card"><div class="k">近4日区间</div><div class="v">${fmt(A.lo,0)} ~ ${fmt(A.hi,0)}</div></div>`;
  document.getElementById("ind").innerHTML = `
    <tr><th>指标</th><th>当前值</th><th>判断</th></tr>
    <tr><td>MA20</td><td>${fmt(A.ma20,0)}</td><td class="${A.price>=A.ma20?"up":"down"}">价格${A.price>=A.ma20?"上方":"下方"}</td></tr>
    <tr><td>MA50</td><td>${fmt(A.ma50,0)}</td><td class="${A.price>=A.ma50?"up":"down"}">价格${A.price>=A.ma50?"上方":"下方"}</td></tr>
    <tr><td>RSI(14)</td><td>${fmt(rNow,1)}</td><td class="${rNow>=70?"down":rNow<=30?"up":"flat"}">${rNow>=70?"超买":rNow<=30?"超卖":"中性"}</td></tr>
    <tr><td>MACD</td><td>${fmt(A.macd,1)}</td><td class="${A.macd>=0?"up":"down"}">${A.macd>=0?"多头":"空头"}</td></tr>
    <tr><td>MACD 柱</td><td>${fmt(histNow,1)}</td><td class="${histNow>=0?"up":"down"}">${histNow>=0?"动能增强":"动能转弱"}</td></tr>`;
  document.getElementById("levels").innerHTML = `
    <tr><th>类型</th><th>价位</th><th>说明</th></tr>
    <tr><td class="down">区间上沿</td><td>${fmt(A.hi,0)}</td><td>近96小时高点</td></tr>
    <tr><td>斐波那契 0.382</td><td>${fmt(A.fib382,0)}</td><td>回撤参考位</td></tr>
    <tr><td class="up">区间下沿</td><td>${fmt(A.lo,0)}</td><td>近96小时低点</td></tr>`;
  const dirMap = {bullish:["看多","bull"],bearish:["看空","bear"],neutral:["中性","neutral"]};
  const [dc, cls] = dirMap[INST.direction] || ["未知","neutral"];
  let rows = "";
  const dm = {funding:"资金费率",oi:"持仓量变化",taker:"主动买卖量",ls:"多空账户",top:"大户持仓"};
  for (const [k,v] of Object.entries(INST.details||{})) rows += `<div class="inst-row"><span>${dm[k]||k}</span><span class="${v.score>0?"pos":v.score<0?"neg":""}">${v.score>=0?"+":""}${fmt(v.score)} · ${v.note||""}</span></div>`;
  document.getElementById("inst").innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><span style="font-size:16px;font-weight:700">机构信号</span><span class="badge ${cls}">${dc} · ${INST.score>=0?"+":""}${fmt(INST.score)}</span></div><div class="inst-rows">${rows}</div>`;
}
render();
</script></body></html>"""
    return (page.replace("{CSS}", CSS).replace("{NAV}", NAV)
                .replace("__UPDATED__", snap.get("updated", "—"))
                .replace("__ANALYSIS__", analysis_json)
                .replace("__INST__", inst_json))


def ledger_page(signals):
    closed = [s for s in signals if s.get("status") == "closed"]
    wins = [s for s in closed if s.get("outcome") == "win"]
    losses = [s for s in closed if s.get("outcome") == "loss"]
    rs = []
    for s in closed:
        risk = abs(s["entry"] - s["sl"])
        rew = abs(s["tp"] - s["entry"])
        rs.append(rew/risk if s["outcome"] == "win" else -1.0)
    gwin = sum(max(x,0) for x in rs)
    gloss = sum(-x for x in rs if x < 0)
    pf = gwin/gloss if gloss else None
    pf_txt = "—" if pf is None else f"{pf:.2f}"
    stats = f"""
    <div class="card"><div class="k">总信号</div><div class="v">{len(signals)}</div></div>
    <div class="card"><div class="k">已平仓</div><div class="v">{len(closed)}</div></div>
    <div class="card"><div class="k">胜率</div><div class="v">{len(wins)/len(closed)*100 if closed else 0:.1f}%</div></div>
    <div class="card"><div class="k">平均R</div><div class="v">{sum(rs)/len(rs) if rs else 0:.2f}</div></div>
    <div class="card"><div class="k">盈利因子</div><div class="v">{pf_txt}</div></div>"""
    rows = ""
    for s in reversed(signals):
        cls = "win" if s.get("outcome") == "win" else "loss" if s.get("outcome") == "loss" else "open"
        txt = "盈利" if s.get("outcome") == "win" else "亏损" if s.get("outcome") == "loss" else "进行中"
        risk = abs(s["entry"] - s["sl"])
        rew = abs(s["tp"] - s["entry"])
        r = (rew/risk) if s.get("outcome") == "win" else -1 if s.get("outcome") == "loss" else "—"
        exit_px = s.get("exit_price")
        exit_txt = "—" if exit_px is None else f"{exit_px:,.0f}"
        rows += (
            f"<tr><td>{s['id']}</td><td>{'多' if s['direction']=='long' else '空'}</td>"
            f"<td>{s['symbol']}</td><td>{s['timeframe']}</td>"
            f"<td>{s['entry']:,.0f}</td><td>{s['sl']:,.0f}</td><td>{s['tp']:,.0f}</td>"
            f"<td>{exit_txt}</td>"
            f"<td>{r}</td><td><span class='pill {cls}'>{txt}</span></td>"
            f"<td>{(s.get('published_at') or '')[:16]}</td></tr>"
        )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kairo Hub · 信号账本</title>{CSS}</head><body><div class="wrap">
{NAV}
<header><div><h1>信号账本</h1><div class="sub">所有信号一经发布不可修改，结果由实时价格自动判定</div></div>
<div class="disclaimer">R 为盈亏倍数：止盈距离 ÷ 止损距离（亏损记 -1）。</div></header>
<div class="grid">{stats}</div>
<table><tr><th>ID</th><th>方向</th><th>标的</th><th>周期</th><th>入场</th><th>止损</th><th>止盈</th><th>出场价</th><th>R</th><th>结果</th><th>发布时间</th></tr>{rows}</table>
<p class="note">免责声明：信号账本仅作统计记录，不构成投资建议。</p>
</div></body></html>"""


def main():
    report = load_json(os.path.join(HERE, "report.json"), {})
    inst = load_json(os.path.join(HERE, "institutional_signal.json"), {})
    signals = load_signals()
    files = {
        "index.html": index_page(report, signals, inst),
        "analysis.html": analysis_page(inst),
        "ledger.html": ledger_page(signals),
    }
    for name, content in files.items():
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            f.write(content)
        print(f"生成 {name} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    main()

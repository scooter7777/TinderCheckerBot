#!/usr/bin/env python3
"""把 report.json + signals.jsonl 渲染成自包含的 dashboard.html。"""

import html, json, os, sys

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


def load_inst():
    return load_json(os.path.join(HERE, "institutional_signal.json"), {})


def main():
    report = load_json(os.path.join(HERE, "report.json"), {})
    signals = load_signals()
    inst = load_inst()
    data = {"report": report, "signals": signals[-50:], "inst": inst}
    payload = json.dumps(data, ensure_ascii=False)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>透明战绩中心</title>
<style>
  :root {{
    --bg:#0d1117; --panel:#161b22; --line:#30363d; --txt:#e6edf3;
    --muted:#8b949e; --green:#3fb950; --red:#f85149; --amber:#d29922; --accent:#58a6ff;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--txt); font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; padding:28px; }}
  .wrap {{ max-width:1100px; margin:0 auto; }}
  header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:1px solid var(--line); padding-bottom:16px; margin-bottom:24px; }}
  h1 {{ font-size:24px; font-weight:700; }}
  .sub {{ color:var(--muted); font-size:13px; margin-top:6px; }}
  .disclaimer {{ color:var(--muted); font-size:12px; max-width:520px; text-align:right; }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:28px; }}
  .kpi {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }}
  .kpi .label {{ color:var(--muted); font-size:12px; }}
  .kpi .value {{ font-size:26px; font-weight:700; margin-top:6px; font-variant-numeric:tabular-nums; }}
  .up {{ color:var(--green); }} .down {{ color:var(--red); }}
  h2 {{ font-size:16px; margin:26px 0 12px; }}
  table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
  th,td {{ padding:10px 12px; text-align:left; font-size:13px; border-bottom:1px solid var(--line); }}
  th {{ background:#1c2129; color:var(--muted); font-weight:600; }}
  tr:last-child td {{ border-bottom:none; }}
  .pill {{ display:inline-block; padding:2px 10px; border-radius:99px; font-size:12px; }}
  .pill.win {{ background:rgba(63,185,80,.12); color:var(--green); }}
  .pill.loss {{ background:rgba(248,81,73,.12); color:var(--red); }}
  .pill.open {{ background:rgba(210,153,34,.12); color:var(--amber); }}
  .note {{ color:var(--muted); font-size:12px; margin-top:20px; line-height:1.7; }}
  .inst {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; margin-bottom:24px; }}
  .inst-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }}
  .inst-dir {{ font-size:22px; font-weight:700; }}
  .badge {{ display:inline-block; padding:4px 14px; border-radius:99px; font-size:14px; font-weight:600; margin-left:10px; }}
  .badge.bull {{ background:rgba(63,185,80,.15); color:var(--green); }}
  .badge.bear {{ background:rgba(248,81,73,.15); color:var(--red); }}
  .badge.neutral {{ background:rgba(139,148,158,.15); color:var(--muted); }}
  .inst-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }}
  .inst-cell {{ border:1px solid var(--line); border-radius:6px; padding:10px 12px; }}
  .inst-cell .k {{ color:var(--muted); font-size:11px; }}
  .inst-cell .v {{ font-size:16px; font-weight:600; margin-top:4px; font-variant-numeric:tabular-nums; }}
  .inst-rows {{ margin-top:14px; }}
  .inst-row {{ display:flex; justify-content:space-between; padding:8px 2px; border-bottom:1px dashed var(--line); font-size:13px; }}
  .inst-row:last-child {{ border-bottom:none; }}
  .inst-row .d {{ color:var(--muted); }}
  .pos {{ color:var(--green); }} .neg {{ color:var(--red); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>透明战绩中心</h1>
      <div class="sub" id="meta"></div>
    </div>
    <div class="disclaimer" id="disc"></div>
  </header>

  <div class="inst" id="inst"></div>

  <div class="kpis" id="kpis"></div>

  <h2>策略回测报告（真实历史数据）</h2>
  <table id="bt"></table>

  <h2>实盘信号账本（公开可验证）</h2>
  <table id="ledger"></table>

  <p class="note">免责声明：回测与信号统计均基于历史真实行情，未做前视偏差处理；历史表现不保证未来收益，本页面不构成投资建议。所有信号一经发布不可修改，结果由价格自动判定。</p>
</div>

<script>
const DATA = {payload};

function fmt(n, d=2) {{
  if (n == null || !isFinite(n)) return "—";
  return Number(n).toLocaleString("en-US", {{maximumFractionDigits:d, minimumFractionDigits:d}});
}}
function sign(n, suffix="%") {{
  if (n == null || !isFinite(n)) return "—";
  return (n>0?"+":"") + fmt(n) + suffix;
}}

const report = DATA.report || {{}};
const strats = report.strategies || {{}};
const inst = DATA.inst || {{}};

document.getElementById("meta").textContent =
  (report.asset || "—") + " · " + (report.start || "") + " → " + (report.end || "") +
  " · " + (report.bars || 0) + " 根K线 · 生成于 " + (report.generated_at || "").slice(0,19);
document.getElementById("disc").textContent = report.disclaimer || "";

const instEl = document.getElementById("inst");
const dirMap = {{bullish:["看多","bull"], bearish:["看空","bear"], neutral:["中性","neutral"]}};
const [dirCn, dirCls] = dirMap[inst.direction] || ["未知","neutral"];
const score = inst.score;
const scoreCls = score > 0 ? "pos" : score < 0 ? "neg" : "";
let instHtml = `
  <div class="inst-head">
    <div><span class="inst-dir">真实机构信号</span><span class="badge ${{dirCls}}">${{dirCn}} · ${{fmt(inst.score)}}</span></div>
    <div class="sub">${{inst.symbol||"—"}} · ${{(inst.generated_at||"").slice(0,19).replace("T"," ")}}</div>
  </div>
  <div class="inst-grid">
    <div class="inst-cell"><div class="k">标记价格</div><div class="v">$${{fmt(inst.mark_price,0)}}</div></div>
    <div class="inst-cell"><div class="k">资金费率</div><div class="v">${{inst.funding_rate==null?"—":fmt(inst.funding_rate*100,3)+"%"}}</div></div>
    <div class="inst-cell"><div class="k">持仓量</div><div class="v">${{fmt(inst.open_interest,0)}} BTC</div></div>
    <div class="inst-cell"><div class="k">主动买/卖</div><div class="v">${{fmt(inst.taker_ratio)}}</div></div>
    <div class="inst-cell"><div class="k">多空账户比</div><div class="v">${{fmt(inst.long_short_ratio)}}</div></div>
    <div class="inst-cell"><div class="k">大户持仓比</div><div class="v">${{fmt(inst.top_position_ratio)}}</div></div>
  </div>
  <div class="inst-rows">`;
const detailMap = {{funding:"资金费率", oi:"持仓量变化", taker:"主动买卖量", ls:"多空账户", top:"大户持仓"}};
for (const [k, v] of Object.entries(inst.details || {{}})) {{
  const c = v.score > 0 ? "pos" : v.score < 0 ? "neg" : "";
  instHtml += `<div class="inst-row"><span>${{detailMap[k]||k}}</span><span class="${{c}}">${{fmt(v.score)}} · ${{v.note||""}}</span></div>`;
}}
instHtml += `</div>`;
instEl.innerHTML = instHtml;

const kpis = document.getElementById("kpis");
const cards = [
  ["组合胜率", "combo_win", "%", "up"],
  ["组合盈利因子", "combo_pf", "", "up"],
  ["组合总收益", "combo_return", "%", "up"],
  ["组合最大回撤", "combo_dd", "%", "down"],
  ["组合交易数", "combo_trades", " 笔", ""],
];
cards.forEach(([label, key, suffix, cls]) => {{
  const m = strats.combo?.metrics || {{}};
  const map = {{combo_win:"胜率%", combo_pf:"盈亏比", combo_return:"总收益%", combo_dd:"最大回撤%", combo_trades:"交易次数"}};
  const v = m[map[key]];
  const el = document.createElement("div");
  el.className = "kpi";
  el.innerHTML = `<div class="label">${{label}}</div><div class="value ${{cls}}">${{v==null?"—":fmt(v)+suffix}}</div>`;
  kpis.appendChild(el);
}});

const bt = document.getElementById("bt");
let html = "<tr><th>策略</th><th>总收益</th><th>年化</th><th>最大回撤</th><th>胜率</th><th>盈亏比</th><th>夏普</th><th>交易数</th></tr>";
for (const [name, r] of Object.entries(strats)) {{
  const m = r.metrics || {{}};
  html += `<tr><td>${{name}}</td><td>${{sign(m["总收益%"])}}</td><td>${{sign(m["年化%"])}}</td>` +
    `<td>${{sign(m["最大回撤%"])}}</td><td>${{fmt(m["胜率%"])}}%</td><td>${{fmt(m["盈亏比"])}}</td>` +
    `<td>${{fmt(m["夏普"])}}</td><td>${{m["交易次数"]}}</td></tr>`;
}}
bt.innerHTML = html;

const lg = document.getElementById("ledger");
const rows = DATA.signals || [];
if (!rows.length) {{
  lg.innerHTML = "<tr><td>暂无已发布信号</td></tr>";
}} else {{
  let lh = "<tr><th>ID</th><th>方向</th><th>标的</th><th>周期</th><th>入场</th><th>止损</th><th>止盈</th><th>状态</th><th>结果</th><th>发布时间</th></tr>";
  [...rows].reverse().forEach(r => {{
    const cls = r.outcome === "win" ? "win" : r.outcome === "loss" ? "loss" : "open";
    const txt = r.outcome === "win" ? "盈利" : r.outcome === "loss" ? "亏损" : "进行中";
    lh += `<tr><td>${{r.id}}</td><td>${{r.direction==="long"?"多":"空"}}</td><td>${{r.symbol}}</td><td>${{r.timeframe}}</td>` +
      `<td>${{fmt(r.entry,0)}}</td><td>${{fmt(r.sl,0)}}</td><td>${{fmt(r.tp,0)}}</td>` +
      `<td><span class="pill ${{cls}}">${{txt}}</span></td><td>${{r.exit_price==null?"—":fmt(r.exit_price,0)}}</td>` +
      `<td>${{(r.published_at||"").slice(0,16)}}</td></tr>`;
  }});
  lg.innerHTML = lh;
}}
</script>
</body>
</html>
"""
    out = os.path.join(HERE, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"dashboard.html 已生成 ({len(page)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

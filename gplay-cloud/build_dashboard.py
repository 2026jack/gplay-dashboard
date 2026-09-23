# -*- coding: utf-8 -*-
"""生成 Momcozy Google Play 评分看板 HTML (本地CDN版 + 平台vendor版)"""
import io, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

with io.open(os.path.join(BASE, "data.json"), encoding="utf-8") as f:
    DATA = json.load(f)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Momcozy · Google Play 评分看板</title>
<style>
:root{--bg:#f4f5f7;--card:#ffffff;--text:#1b1e27;--muted:#6b7280;--line:#e5e7eb;
--s5:#1e9e6a;--s4:#7cc08b;--s3:#ef9f27;--s2:#f07a3f;--s1:#e04b4a;--brand:#2f5fd0;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:14px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:20px 16px 48px;overflow-x:hidden}
.hd{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:8px;margin-bottom:14px}
.hd h1{font-size:20px;font-weight:600}
.hd .sub{color:var(--muted);font-size:12px}
.refresh{display:inline-flex;align-items:center;gap:6px;background:var(--card);border:1px solid var(--line);
border-radius:8px;padding:6px 12px;font-size:12px;color:var(--muted)}
.refresh b{color:var(--text);font-variant-numeric:tabular-nums}
.dot{width:8px;height:8px;border-radius:50%;background:var(--s5);display:inline-block}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card .k{color:var(--muted);font-size:12px;margin-bottom:4px}
.card .v{font-size:30px;font-weight:600;font-variant-numeric:tabular-nums}
.card .n{color:var(--muted);font-size:11px;margin-top:4px}
.card .s5{margin-top:8px;font-size:11px;color:var(--muted);display:flex;justify-content:space-between;align-items:center;gap:8px}
.card .s5 b{color:var(--text);font-size:13px;font-variant-numeric:tabular-nums}
.card .s5 .bar{flex:1;max-width:72px}
.card.gl .v{color:var(--brand)}.card.us .v{color:var(--s5)}
.sec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:14px}
.sec h2{font-size:15px;font-weight:600;margin-bottom:12px;display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px}
.sec h2 .tag{font-size:11px;color:var(--muted);font-weight:400}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:right;color:var(--muted);font-weight:500;font-size:12px;padding:7px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{text-align:right;padding:7px 8px;border-bottom:1px solid #f0f1f3;font-variant-numeric:tabular-nums;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
tr:last-child td{border-bottom:none}
tr.total td{font-weight:600;border-top:2px solid var(--line);background:#fafbfc}
.pct{color:var(--muted);font-size:11px}
.bar{height:6px;border-radius:3px;background:#eef0f2;overflow:hidden;min-width:60px}
.bar i{display:block;height:100%;border-radius:3px}
.c5{background:var(--s5)}.c4{background:var(--s4)}.c3{background:var(--s3)}.c2{background:var(--s2)}.c1{background:var(--s1)}
.tblwrap{overflow-x:auto}
.tbox svg{width:100%;height:auto;display:block}
.tabs{display:flex;gap:8px;margin-bottom:10px}
.tabs button{border:1px solid var(--line);background:#fff;border-radius:8px;padding:5px 14px;font-size:13px;cursor:pointer;color:var(--muted)}
.tabs button.on{background:var(--text);color:#fff;border-color:var(--text)}
.frow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px;font-size:12px;color:var(--muted)}
.frow input[type=date]{border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;color:var(--text)}
.frow button{border:1px solid var(--line);background:#fff;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer;color:var(--muted)}
.frow button.on{background:#eef2fd;color:var(--brand);border-color:#c9d7f7}
.note{color:var(--muted);font-size:11px;margin-top:8px;line-height:1.6}
.vwrap{max-height:420px;overflow:auto;border:1px solid #f0f1f3;border-radius:8px}
.vwrap table{margin:0}
.empty{color:var(--muted);padding:18px 4px;font-size:13px}
@media (max-width:640px){.card .v{font-size:24px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hd">
    <div>
      <h1>Momcozy · Google Play 评分看板</h1>
      <div class="sub">com.lute.momcozy · 数据源：Play 官方批量报告 + 评论 API + 商店快照 · 每日 09:00 自动更新</div>
    </div>
    <div class="refresh"><span class="dot"></span>数据刷新时间 <b id="rtime"></b></div>
  </div>

  <div class="cards">
    <div class="card gl"><div class="k">全球评分值</div><div class="v" id="g-val">-</div><div class="n" id="g-val-n"></div><div class="s5" id="g-val-s5"></div></div>
    <div class="card gl"><div class="k">全球评分数</div><div class="v" id="g-cnt">-</div><div class="n" id="g-cnt-n"></div><div class="s5" id="g-cnt-s5"></div></div>
    <div class="card us"><div class="k">美国评分值</div><div class="v" id="u-val">-</div><div class="n" id="u-val-n"></div><div class="s5" id="u-val-s5"></div></div>
    <div class="card us"><div class="k">美国评分数</div><div class="v" id="u-cnt">-</div><div class="n" id="u-cnt-n"></div><div class="s5" id="u-cnt-s5"></div></div>
  </div>

  <div class="sec">
    <h2>评分趋势<span class="tag">总评分（累计评分值）· 支持日期筛选</span></h2>
    <div class="frow">
      <span>日期</span>
      <input type="date" id="t-start">
      <span>至</span>
      <input type="date" id="t-end">
      <button id="tq7">近7天</button><button id="tq30">近30天</button><button id="tqall">全部</button>
    </div>
    <div class="grid2">
      <div>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">全球评分趋势</div>
        <div class="tbox" id="ch-g"></div>
      </div>
      <div>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">美国评分趋势</div>
        <div class="tbox" id="ch-u"></div>
      </div>
    </div>
    <div class="note">纵轴为总评分（累计评分值，即商店展示口径随时间的走势），来自 Play 官方批量报告，官方保留近 2 个月历史，每日 09:00 自动追加。悬停数据点可看当日分值。</div>
  </div>

  <div class="sec">
    <h2>星级分布<span class="tag">数量与占比</span></h2>
    <div class="grid2">
      <div>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">全球（官方批量报告·累计书面评论）</div>
        <div class="tblwrap"><table id="t-gl"></table></div>
      </div>
      <div>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">美国（商店页面显示口径）</div>
        <div class="tblwrap"><table id="t-us"></table></div>
      </div>
    </div>
    <div class="note">全球分布来自 Play 官方批量报告的全量书面评论历史（2024-02 起回填）；美国分布为 Play 商店页面公开展示的星级分布（含纯打星）。</div>
  </div>

  <div class="sec">
    <h2>每日新增评分数<span class="tag">支持日期筛选</span></h2>
    <div class="tabs"><button id="tab-gl" class="on">全球</button><button id="tab-us">美国</button></div>
    <div class="frow">
      <span>日期</span>
      <input type="date" id="d-start">
      <span>至</span>
      <input type="date" id="d-end">
      <button id="q7">近7天</button><button id="q30">近30天</button><button id="qall">全部</button>
    </div>
    <div class="tblwrap"><table id="t-daily"></table></div>
    <div class="note">全球口径来自官方批量报告的全量评论历史（2024-02 起回填，近几日由 API 实时补齐）；美国为商店评论全量历史。均为书面评论，不含纯打星。</div>
  </div>

  <div class="sec">
    <h2>App 版本分布<span class="tag">不同版本各星级评论数</span></h2>
    <div class="grid2">
      <div>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">全球（官方批量报告·按版本）</div>
        <div class="vwrap"><table id="t-vg"></table></div>
      </div>
      <div>
        <div style="font-weight:600;font-size:13px;margin-bottom:8px">美国（商店评论，按版本）</div>
        <div class="vwrap"><table id="t-vu"></table></div>
      </div>
    </div>
    <div class="note">按评论发生时的 App 版本统计；全球口径来自官方批量报告全量历史，美国为商店评论全量历史（含版本号自解析）。</div>
  </div>
</div>
<script>
const DATA = __DATA__;
const STARS = [5,4,3,2,1];
const fmt = n => (n||0).toLocaleString("en-US");
const pct = (n, t) => t > 0 ? (100*n/t).toFixed(1) + "%" : "0.0%";
document.getElementById("rtime").textContent = DATA.generated_at;

(function(){
  const g = DATA.global, u = DATA.us, off = DATA.official || {}, anc = DATA.anchor || {};
  document.getElementById("g-val").textContent = anc.global_default_rating != null ? Number(anc.global_default_rating).toFixed(3) : "-";
  document.getElementById("g-val-n").textContent = "后台·默认 Google Play 评分（全量含纯打星·锚定 " + (anc.anchored_at||"") + "）";
  document.getElementById("g-cnt").textContent = fmt(g.rating_count);
  document.getElementById("g-cnt-n").textContent = "全部评分人数 = 评论 + 仅打星（商店展示口径）";
  document.getElementById("u-val").textContent = u.hist_avg != null ? u.hist_avg.toFixed(2) : "-";
  document.getElementById("u-val-n").textContent = "美国区全量精确值（含纯打星·由星级分布实时计算，与后台默认评分 " + (anc.us_default_rating||"-") + " 一致）";
  document.getElementById("u-cnt").textContent = fmt(u.hist_sum);
  document.getElementById("u-cnt-n").textContent = "美国全部评分人数 = 评论 + 仅打星";

  // 四卡下方: 5星占比 (全球=官方书面评论口径; 美国=商店全量含纯打星)
  function starShare(hist){
    let five = 0, total = 0;
    STARS.forEach(s => { const n = hist[String(s)]||0; total += n; if (s===5) five = n; });
    return total > 0 ? (100*five/total) : null;
  }
  const gShare = starShare(g.hist_from_reviews||{});
  const uShare = starShare(u.hist||{});
  function renderS5(id, share){
    const el = document.getElementById(id);
    if (!el) return;
    if (share == null){ el.innerHTML = "<span>5星占比</span><b>-</b>"; return; }
    el.innerHTML = "<span>5星占比</span><b>" + share.toFixed(1) + "%</b>" +
      "<div class='bar'><i class='c5' style='width:" + share.toFixed(1) + "%'></i></div>";
  }
  renderS5("g-val-s5", gShare);
  renderS5("g-cnt-s5", gShare);
  renderS5("u-val-s5", uShare);
  renderS5("u-cnt-s5", uShare);
})();

function distTable(tid, hist, sum){
  let rows = "<tr><th>星级</th><th>数量</th><th>占比</th><th style='text-align:left;padding-left:16px'>分布</th></tr>";
  STARS.forEach(s => {
    const n = hist[String(s)] || 0;
    rows += "<tr><td>" + "★".repeat(s) + " " + s + "星</td><td>" + fmt(n) +
      "</td><td><span class='pct'>" + pct(n, sum) + "</span></td>" +
      "<td style='text-align:left;padding-left:16px'><div class='bar'><i class='c" + s +
      "' style='width:" + (sum>0?100*n/sum:0) + "%'></i></div></td></tr>";
  });
  rows += "<tr class='total'><td>合计</td><td>" + fmt(sum) + "</td><td>100%</td><td></td></tr>";
  document.getElementById(tid).innerHTML = rows;
}
distTable("t-gl", DATA.global.hist_from_reviews, DATA.global.hist_sum||0);
distTable("t-us", DATA.us.hist||{}, DATA.us.hist_sum||0);

// ---------- 评分趋势(纯SVG折线, 无外部依赖) ----------
const trendG = (DATA.overview.trend||[]).filter(r => r.avg > 0);
const trendU = (DATA.overview.trend_us||[]).filter(r => r.avg > 0);
function drawLine(boxId, pts, color){
  const box = document.getElementById(boxId);
  if (!pts.length){ box.innerHTML = "<div class='empty'>该区间暂无数据</div>"; return; }
  const W=640, H=240, PL=36, PR=12, PT=14, PB=24, iw=W-PL-PR, ih=H-PT-PB;
  const vals = pts.map(p=>p.avg);
  const ymin = Math.max(1, Math.floor((Math.min(...vals)-0.15)*10)/10);
  const ymax = Math.min(5, Math.ceil((Math.max(...vals)+0.15)*10)/10);
  const X = i => PL + (pts.length===1 ? iw/2 : i*(iw/(pts.length-1)));
  const Y = v => PT + ih*(1-(v-ymin)/(ymax-ymin));
  let grid = "";
  for (let k=0; k<=4; k++){
    const v = ymin + (ymax-ymin)*k/4;
    grid += "<line x1='"+PL+"' y1='"+Y(v)+"' x2='"+(W-PR)+"' y2='"+Y(v)+"' stroke='#eef0f2' stroke-width='1'/>" +
      "<text x='"+(PL-6)+"' y='"+(Y(v)+4)+"' text-anchor='end' font-size='10' fill='#9aa1ad'>"+v.toFixed(1)+"</text>";
  }
  const line = pts.map((p,i)=>X(i).toFixed(1)+","+Y(p.avg).toFixed(1)).join(" ");
  const area = PL+","+Y(ymin)+" "+line+" "+X(pts.length-1).toFixed(1)+","+Y(ymin);
  const step = Math.max(1, Math.round(pts.length/10));
  let dots = "";
  pts.forEach((p,i)=>{
    if (i%step===0 || i===pts.length-1){
      dots += "<circle cx='"+X(i).toFixed(1)+"' cy='"+Y(p.avg).toFixed(1)+"' r='2.6' fill='"+color+"'><title>"+p.date+"："+p.avg.toFixed(2)+"★</title></circle>";
    }
  });
  const mean = pts.reduce((a,p)=>a+p.avg,0)/pts.length;
  box.innerHTML = "<svg viewBox='0 0 "+W+" "+H+"'>" + grid +
    "<polygon points='"+area+"' fill='"+color+"' opacity='0.08'/>" +
    "<polyline points='"+line+"' fill='none' stroke='"+color+"' stroke-width='2' stroke-linejoin='round' stroke-linecap='round'/>" +
    dots +
    "<text x='"+PL+"' y='"+(H-6)+"' font-size='10' fill='#9aa1ad'>"+pts[0].date.slice(5)+"</text>" +
    "<text x='"+(W-PR)+"' y='"+(H-6)+"' text-anchor='end' font-size='10' fill='#9aa1ad'>"+pts[pts.length-1].date.slice(5)+"</text>" +
    "<text x='"+(W-PR)+"' y='"+(PT+4)+"' text-anchor='end' font-size='11' fill='#1b1e27'>区间均分 "+mean.toFixed(2)+"★</text>" +
    "</svg>";
}
function renderTrend(){
  const s = document.getElementById("t-start").value, e = document.getElementById("t-end").value;
  drawLine("ch-g", trendG.filter(r => (!s || r.date >= s) && (!e || r.date <= e)), "#2f5fd0");
  drawLine("ch-u", trendU.filter(r => (!s || r.date >= s) && (!e || r.date <= e)), "#1e9e6a");
}
function tQuick(days){
  const end = new Date().toISOString().slice(0,10);
  const start = new Date(Date.now() - (days-1)*86400000).toISOString().slice(0,10);
  document.getElementById("t-start").value = start;
  document.getElementById("t-end").value = end;
  document.getElementById("tq7").className = days===7?"on":"";
  document.getElementById("tq30").className = days===30?"on":"";
  document.getElementById("tqall").className = "";
  renderTrend();
}
document.getElementById("t-start").onchange = () => {
  document.getElementById("tq7").className="";document.getElementById("tq30").className="";document.getElementById("tqall").className="";
  renderTrend();
};
document.getElementById("t-end").onchange = document.getElementById("t-start").onchange;
document.getElementById("tq7").onclick = () => tQuick(7);
document.getElementById("tq30").onclick = () => tQuick(30);
document.getElementById("tqall").onclick = () => {
  const dates = trendG.concat(trendU).map(r=>r.date).sort();
  if (dates.length){
    document.getElementById("t-start").value = dates[0];
    document.getElementById("t-end").value = dates[dates.length-1];
  }
  document.getElementById("tq7").className="";document.getElementById("tq30").className="";document.getElementById("tqall").className="on";
  renderTrend();
};
if (trendG.length) tQuick(30); else if (trendU.length) tQuick(30);

let dailyRegion = "gl";
function dailyRows(){
  return dailyRegion === "gl" ? (DATA.daily_new||[]) : (DATA.daily_new_us||[]);
}
function renderDaily(){
  const s = document.getElementById("d-start").value, e = document.getElementById("d-end").value;
  let rows = dailyRows().filter(r => (!s || r.date >= s) && (!e || r.date <= e));
  rows = rows.slice().reverse();
  let html = "<tr><th>日期</th><th>5星</th><th>4星</th><th>3星</th><th>2星</th><th>1星</th><th>总计</th></tr>";
  if (!rows.length){
    html += "<tr><td colspan='7' class='empty'>该区间暂无数据（全球口径自 " + DATA.start_date + " 起每日累积）</td></tr>";
  } else {
    let t = {s1:0,s2:0,s3:0,s4:0,s5:0,total:0};
    rows.forEach(r => {
      t.s1+=r.s1;t.s2+=r.s2;t.s3+=r.s3;t.s4+=r.s4;t.s5+=r.s5;t.total+=r.total;
      html += "<tr><td>" + r.date + "</td><td>" + r.s5 + "</td><td>" + r.s4 + "</td><td>" + r.s3 +
        "</td><td>" + r.s2 + "</td><td>" + r.s1 + "</td><td><b>" + r.total + "</b></td></tr>";
    });
    html += "<tr class='total'><td>合计（" + rows.length + " 天）</td><td>" + t.s5 + "</td><td>" + t.s4 +
      "</td><td>" + t.s3 + "</td><td>" + t.s2 + "</td><td>" + t.s1 + "</td><td>" + t.total + "</td></tr>";
  }
  document.getElementById("t-daily").innerHTML = html;
}
function setRegion(rg){
  dailyRegion = rg;
  document.getElementById("tab-gl").className = rg==="gl" ? "on" : "";
  document.getElementById("tab-us").className = rg==="us" ? "on" : "";
  const all = dailyRows();
  if (all.length){
    document.getElementById("d-start").value = all[0].date;
    document.getElementById("d-end").value = all[all.length-1].date;
  }
  renderDaily();
}
document.getElementById("tab-gl").onclick = () => setRegion("gl");
document.getElementById("tab-us").onclick = () => setRegion("us");
document.getElementById("d-start").onchange = renderDaily;
document.getElementById("d-end").onchange = renderDaily;
function quick(days){
  const end = new Date().toISOString().slice(0,10);
  const start = new Date(Date.now() - (days-1)*86400000).toISOString().slice(0,10);
  document.getElementById("d-start").value = start;
  document.getElementById("d-end").value = end;
  document.getElementById("q7").className = days===7?"on":"";
  document.getElementById("q30").className = days===30?"on":"";
  document.getElementById("qall").className = "";
  renderDaily();
}
document.getElementById("q7").onclick = () => quick(7);
document.getElementById("q30").onclick = () => quick(30);
document.getElementById("qall").onclick = () => {
  const all = dailyRows();
  if (all.length){
    document.getElementById("d-start").value = all[0].date;
    document.getElementById("d-end").value = all[all.length-1].date;
  }
  document.getElementById("q7").className="";document.getElementById("q30").className="";
  document.getElementById("qall").className="on";
  renderDaily();
};
quick(30);

function versionTable(tid, arr){
  let html = "<tr><th>版本</th><th>5星</th><th>4星</th><th>3星</th><th>2星</th><th>1星</th><th>总计</th><th>均分</th></tr>";
  if (!arr.length){
    html += "<tr><td colspan='8' class='empty'>暂无版本数据</td></tr>";
  } else arr.forEach(v => {
    const w = v.s1+2*v.s2+3*v.s3+4*v.s4+5*v.s5;
    const avg = v.total > 0 ? (w/v.total).toFixed(2) : "-";
    html += "<tr><td>" + v.version + "</td><td>" + v.s5 + "</td><td>" + v.s4 + "</td><td>" + v.s3 +
      "</td><td>" + v.s2 + "</td><td>" + v.s1 + "</td><td><b>" + v.total + "</b></td><td>" + avg + "</td></tr>";
  });
  document.getElementById(tid).innerHTML = html;
}
versionTable("t-vg", DATA.version_global||[]);
versionTable("t-vu", DATA.version_us||[]);
</script>
</body>
</html>
"""

html = (TEMPLATE
        .replace("__CHARTJS__", "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js")
        .replace("__DATA__", json.dumps(DATA, ensure_ascii=False))
        .replace("__START__", DATA.get("start_date", "")))

with io.open(os.path.join(BASE, "dashboard.html"), "w", encoding="utf-8", newline="\n") as f:
    f.write(html)

platform = html.replace("https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js",
                        "vendor/chart.umd.js")
with io.open(os.path.join(BASE, "dashboard_platform.html"), "w", encoding="utf-8", newline="\n") as f:
    f.write(platform)

print("本地版:", os.path.join(BASE, "dashboard.html"), len(html), "chars")
print("平台版:", os.path.join(BASE, "dashboard_platform.html"), len(platform), "chars")

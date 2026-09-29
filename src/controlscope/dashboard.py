"""Self-contained local dashboard preview from curated finding records."""

from __future__ import annotations

import json
from pathlib import Path

from .pipeline import REGISTRY
from .store import connect, finding_detail

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ControlScope | Audit analytics</title>
<style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#172b35;background:#f5f7f7}
*{box-sizing:border-box}body{margin:0}header{background:#102d38;color:#fff;padding:24px clamp(20px,4vw,64px)}
header h1{margin:0;font-size:27px;letter-spacing:-.04em}header p{margin:6px 0 0;color:#b7d3d7}
main{max-width:1440px;margin:auto;padding:28px clamp(20px,4vw,64px)}
.eyebrow{font-size:11px;font-weight:800;letter-spacing:.11em;text-transform:uppercase;color:#44767d}
.filters{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:22px}label{font-size:12px;font-weight:700}
select{display:block;margin-top:6px;padding:9px 12px;border:1px solid #cbd9dc;border-radius:8px;background:#fff;min-width:160px}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:20px}
.card,.panel{background:#fff;border:1px solid #dfebeb;border-radius:12px;box-shadow:0 2px 8px #173a4208}
.card{padding:18px}.card strong{display:block;font-size:29px;margin-top:7px;letter-spacing:-.04em}
.grid{display:grid;grid-template-columns:1.15fr .85fr;gap:16px;margin-bottom:20px}.panel{padding:19px}
h2{font-size:17px;margin:0 0 16px}.barrow{display:grid;grid-template-columns:150px 1fr 35px;gap:10px;align-items:center;margin:11px 0;font-size:13px}
.track{background:#edf3f3;border-radius:20px;overflow:hidden;height:10px}.fill{height:100%;background:#238e89;border-radius:20px}
.fill.high{background:#ca584b}.fill.medium{background:#e9aa46}.fill.low{background:#4b9a88}
table{border-collapse:collapse;width:100%;font-size:13px}th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#63818a;background:#f6f9f9}
td,th{padding:11px 10px;border-bottom:1px solid #e8eeee;vertical-align:top}tr[data-id]{cursor:pointer}tr[data-id]:hover{background:#f2f8f8}
.pill{padding:4px 8px;border-radius:20px;font-weight:700;font-size:11px;background:#edf3f3;white-space:nowrap}
.pill.high{background:#fcebe8;color:#a43124}.pill.medium{background:#fff2d9;color:#9b6000}.pill.low{background:#e2f3ef;color:#207766}
.tablewrap{overflow:auto;max-height:510px}code{font-size:11px;overflow-wrap:anywhere}
dialog{border:0;border-radius:14px;padding:0;width:min(760px,92vw);max-height:85vh;box-shadow:0 15px 70px #071c2470}
dialog::backdrop{background:#071c2480}.dialoghead{padding:20px 24px;background:#102d38;color:white;display:flex;justify-content:space-between;align-items:center}
.dialoghead h2{margin:0}.dialogbody{padding:22px 24px;overflow:auto;max-height:70vh}.close{border:0;background:#ffffff22;color:#fff;border-radius:7px;padding:7px 11px;cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f7;padding:12px;border-radius:8px;font-size:12px}
.note{color:#607980;font-size:12px;margin-top:18px}@media(max-width:850px){.cards{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}}
</style></head><body>
<header><div class="eyebrow" style="color:#75c9c1">Synthetic audit analytics</div><h1>ControlScope</h1><p>Control coverage, risk, and source-linked findings</p></header>
<main>
<div class="filters"><label>Run<select id="run"></select></label><label>Control<select id="control"></select></label><label>Status<select id="status"></select></label><label>Risk<select id="risk"></select></label></div>
<section class="cards"><div class="card"><span class="eyebrow">Findings</span><strong id="total">0</strong></div><div class="card"><span class="eyebrow">High risk</span><strong id="high">0</strong></div><div class="card"><span class="eyebrow">Controls with hits</span><strong id="coverage">0</strong></div><div class="card"><span class="eyebrow">Open findings</span><strong id="open">0</strong></div></section>
<div class="grid"><section class="panel"><h2>Control coverage</h2><div id="controls"></div></section><section class="panel"><h2>Risk distribution</h2><div id="risks"></div><h2 style="margin-top:24px">Review status</h2><div id="statuses"></div></section></div>
<section class="panel"><h2>Findings and evidence</h2><div class="tablewrap"><table><thead><tr><th>Control</th><th>Entity</th><th>Unit</th><th>Risk</th><th>Status</th><th>Age</th><th>Evidence</th></tr></thead><tbody id="findings"></tbody></table></div><p class="note">Select a finding to inspect source rows and review history. Decisions are recorded through the ControlScope CLI. All displayed data is synthetic.</p></section>
</main><dialog id="detail"><div class="dialoghead"><h2>Finding evidence</h2><button class="close" id="close">Close</button></div><div class="dialogbody" id="detailbody"></div></dialog>
<script>const DATA=__DATA__;
const $=id=>document.getElementById(id); const esc=s=>String(s).replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const band=n=>n>=80?'high':n>=50?'medium':'low';
function options(id,items,all){$(id).innerHTML='<option value="">'+all+'</option>'+items.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join('')}
options('run',[...new Set(DATA.findings.map(f=>f.run_id))],'All runs');
options('control',DATA.registry.map(r=>r.id),'All controls');
options('status',['open','confirmed','dismissed','overridden'],'All statuses');
options('risk',['high','medium','low'],'All risk');
function bars(id,entries,klass){const max=Math.max(1,...entries.map(e=>e[1]));$(id).innerHTML=entries.map(([name,count])=>'<div class="barrow"><span>'+esc(name)+'</span><div class="track"><div class="fill '+(klass?klass(name):'')+'" style="width:'+Math.max(0,100*count/max)+'%"></div></div><strong>'+count+'</strong></div>').join('')}
function render(){const filters=['run','control','status','risk'].map(id=>$(id).value);
const rows=DATA.findings.filter(f=>(!filters[0]||f.run_id===filters[0])&&(!filters[1]||f.control_id===filters[1])&&(!filters[2]||f.status===filters[2])&&(!filters[3]||band(f.current_score)===filters[3]));
$('total').textContent=rows.length;$('high').textContent=rows.filter(f=>f.current_score>=80).length;
$('coverage').textContent=new Set(rows.map(f=>f.control_id)).size+' / '+DATA.registry.length;$('open').textContent=rows.filter(f=>f.status==='open').length;
bars('controls',DATA.registry.map(r=>[r.id,rows.filter(f=>f.control_id===r.id).length]));
bars('risks',['high','medium','low'].map(x=>[x,rows.filter(f=>band(f.current_score)===x).length]),x=>x);
bars('statuses',['open','confirmed','dismissed','overridden'].map(x=>[x,rows.filter(f=>f.status===x).length]));
$('findings').innerHTML=rows.map(f=>{const age=Math.max(0,Math.floor((Date.now()-Date.parse(f.created_at))/86400000));return '<tr data-id="'+esc(f.finding_id)+'"><td>'+esc(f.control_id)+'</td><td><code>'+esc(f.entity_id)+'</code></td><td>'+esc(f.business_unit)+'</td><td><span class="pill '+band(f.current_score)+'">'+f.current_score+'</span></td><td>'+esc(f.status)+'</td><td>'+age+'d</td><td>'+f.evidence.length+' rows</td></tr>'}).join('');
document.querySelectorAll('tr[data-id]').forEach(tr=>tr.onclick=()=>show(tr.dataset.id));}
function show(id){const f=DATA.findings.find(x=>x.finding_id===id);const body=$('detailbody');
body.innerHTML='<p><strong>'+esc(f.control_id)+'</strong> · '+esc(f.entity_id)+' · risk '+f.current_score+' · '+esc(f.status)+'</p><p>'+esc(f.detail)+'</p><h3>Source rows</h3>'+f.evidence.map(e=>'<p><code>'+esc(e.table+'/'+e.row_id)+'</code></p><pre>'+esc(JSON.stringify(e.row,null,2))+'</pre>').join('')+'<h3>Review history</h3>'+(f.review_history.length?f.review_history.map(a=>'<p>'+esc(a.acted_at)+' · '+esc(a.actor)+' · '+esc(a.action)+' · '+esc(a.reason)+' ('+a.original_score+' → '+a.replacement_score+')</p>').join(''):'<p>No review actions yet.</p>');$('detail').showModal()}
['run','control','status','risk'].forEach(id=>$(id).onchange=render);$('close').onclick=()=>$('detail').close();render();
</script></body></html>"""


def write_dashboard(db_path: Path, out_path: Path) -> dict:
    conn = connect(db_path)
    try:
        findings = [finding_detail(conn, row[0]) for row in conn.execute(
            "SELECT finding_id FROM findings ORDER BY finding_id")]
    finally:
        conn.close()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))["controls"]
    payload = json.dumps({"findings": findings, "registry": registry}, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    return {"dashboard": str(out_path), "findings": len(findings)}

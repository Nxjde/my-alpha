"""
research dashboard: research_log.jsonl을 표+그래프로 보여주고,
requests.jsonl에 새 요청을 큐잉하는 간단한 Flask 앱.
"""
from flask import Flask, jsonify, request, render_template_string
import json
import os
from datetime import datetime, timezone

app = Flask(__name__)
LOG_FILE = "research_log.jsonl"
REQ_FILE = "requests.jsonl"


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


@app.route("/api/log")
def api_log():
    return jsonify(load_jsonl(LOG_FILE))


@app.route("/api/requests")
def api_requests():
    return jsonify(load_jsonl(REQ_FILE))


@app.route("/api/submit", methods=["POST"])
def api_submit():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "status": "pending",
    }
    with open(REQ_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return jsonify({"ok": True, "entry": entry})


PAGE = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>my-alpha Research Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  body { font-family: -apple-system, sans-serif; background:#111; color:#eee; margin:0; padding:24px; }
  h1 { font-size:20px; margin-bottom:4px; }
  .sub { color:#888; font-size:13px; margin-bottom:20px; }
  table { width:100%; border-collapse:collapse; margin-bottom:32px; font-size:13px; }
  th, td { border-bottom:1px solid #333; padding:8px 10px; text-align:left; vertical-align:top; }
  th { color:#999; font-weight:600; }
  .go { color:#4ade80; font-weight:600; }
  .nogo { color:#f87171; font-weight:600; }
  .hold { color:#fbbf24; font-weight:600; }
  #chart-wrap { max-width:700px; margin-bottom:32px; }
  textarea { width:100%; box-sizing:border-box; background:#1c1c1c; color:#eee; border:1px solid #333;
             border-radius:6px; padding:10px; font-size:14px; min-height:70px; resize:vertical; }
  button { background:#3b82f6; color:white; border:none; padding:10px 18px; border-radius:6px;
           cursor:pointer; font-size:14px; margin-top:8px; }
  button:hover { background:#2563eb; }
  .req-item { padding:8px 0; border-bottom:1px solid #2a2a2a; font-size:13px; }
  .req-status { color:#888; font-size:11px; }
</style>
</head>
<body>
  <h1>my-alpha Research Dashboard</h1>
  <div class="sub" id="last-updated"></div>

  <div id="chart-wrap"><canvas id="chart"></canvas></div>

  <h2 style="font-size:15px;">시도 기록</h2>
  <table id="log-table">
    <thead><tr><th>아이디어</th><th>가설</th><th>방법</th><th>판정</th><th>이유</th></tr></thead>
    <tbody></tbody>
  </table>

  <h2 style="font-size:15px;">다음 방향 요청</h2>
  <textarea id="req-text" placeholder="예: reversal lookback을 3일로 바꿔서 다시 검증해줘"></textarea>
  <br>
  <button onclick="submitRequest()">요청 제출</button>

  <h2 style="font-size:15px; margin-top:24px;">요청 큐</h2>
  <div id="req-list"></div>

<script>
async function loadLog() {
  const res = await fetch('/api/log');
  const data = await res.json();
  const tbody = document.querySelector('#log-table tbody');
  tbody.innerHTML = '';
  data.forEach(e => {
    const cls = e.verdict === 'GO' ? 'go' : (e.verdict === 'NO-GO' ? 'nogo' : 'hold');
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${e.idea}</td><td>${e.hypothesis||''}</td><td>${e.method||''}</td>
                    <td class="${cls}">${e.verdict}</td><td>${e.reason||''}</td>`;
    tbody.appendChild(tr);
  });
  document.getElementById('last-updated').textContent = `총 ${data.length}개 시도 기록됨`;
  renderChart(data);
}

function renderChart(data) {
  const labels = [];
  const sharpes = [];
  data.forEach(e => {
    if (e.result) {
      for (const [k, v] of Object.entries(e.result)) {
        if (v && typeof v === 'object' && 'sharpe' in v) {
          labels.push(`${e.idea.slice(0,10)}/${k}`);
          sharpes.push(v.sharpe);
        }
      }
    }
  });
  new Chart(document.getElementById('chart'), {
    type: 'bar',
    data: { labels, datasets: [{ label: 'Sharpe', data: sharpes, backgroundColor: '#3b82f6' }] },
    options: { plugins: { legend: { display: false } },
               scales: { y: { ticks: { color: '#ccc' } }, x: { ticks: { color: '#ccc', font: { size: 10 } } } } }
  });
}

async function loadRequests() {
  const res = await fetch('/api/requests');
  const data = await res.json();
  const list = document.getElementById('req-list');
  list.innerHTML = '';
  data.slice().reverse().forEach(r => {
    const div = document.createElement('div');
    div.className = 'req-item';
    div.innerHTML = `${r.text}<br><span class="req-status">${r.status} · ${r.ts}</span>`;
    list.appendChild(div);
  });
}

async function submitRequest() {
  const text = document.getElementById('req-text').value.trim();
  if (!text) return;
  await fetch('/api/submit', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({text})
  });
  document.getElementById('req-text').value = '';
  loadRequests();
}

loadLog();
loadRequests();
setInterval(() => { loadLog(); loadRequests(); }, 15000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

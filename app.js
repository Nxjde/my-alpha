var LOG = [], FILTER = null, VIEW = "list", CH1 = null, CH2 = null;
var ICON = {"GO": "✅", "보류": "🟡", "NO-GO": "⛔"};
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
  });
}
function vcls(v) { return v === "GO" ? "go" : (v === "NO-GO" ? "nogo" : "hold"); }
function pct(x) { return (x * 100).toFixed(1) + "%"; }

function renderCards() {
  var c = LOG.filter(function (e) { return e.counted; });
  function n(v) { return c.filter(function (e) { return e.verdict === v; }).length; }
  var items = [["전체 시도", c.length, null, "📊"], ["GO", n("GO"), "GO", "✅"],
               ["보류", n("보류"), "보류", "🟡"], ["NO-GO", n("NO-GO"), "NO-GO", "⛔"]];
  var html = "";
  items.forEach(function (it, i) {
    var on = (it[2] !== null && FILTER === it[2]) ? " active" : "";
    html += '<div class="card' + on + '" data-i="' + i + '">' +
      '<div style="font-size:22px">' + it[3] + '</div>' +
      '<div class="n ' + (it[2] ? vcls(it[2]) : "") + '">' + it[1] + '</div>' +
      '<div class="t">' + esc(it[0]) + '</div></div>';
  });
  var box = document.getElementById("cards");
  box.innerHTML = html;
  box.querySelectorAll(".card").forEach(function (el) {
    el.onclick = function () { setFilter(items[+el.getAttribute("data-i")][2]); };
  });
}
function setFilter(v) { FILTER = (FILTER === v ? null : v); showList(); }

function renderList() {
  var rows = LOG.filter(function (e) { return !FILTER || (e.counted && e.verdict === FILTER); });
  document.getElementById("filter-note").textContent = FILTER
    ? ("필터: " + FILTER + " (같은 카드를 다시 누르면 해제)")
    : "카드를 누르면 판정별로 걸러 볼 수 있어요. 항목을 누르면 상세가 열려요.";
  var html = "";
  rows.forEach(function (e) {
    var tag = e.supplement ? '<span class="small"> · 정정/보강(집계 제외)</span>' : "";
    var ch = (e.curves && e.curves.length) ? " 📈" : "";
    html += '<tr class="row' + (e.supplement ? " sup" : "") + '" data-id="' + e.id + '">' +
      '<td>' + esc(e.idea) + ch + tag + '</td>' +
      '<td class="badge ' + vcls(e.verdict) + '">' + (ICON[e.verdict] || "") + " " + esc(e.verdict) + '</td>' +
      '<td class="small">' + esc(e.method) + '</td><td class="small">' + esc(e.reason) + '</td></tr>';
  });
  var tb = document.getElementById("rows");
  tb.innerHTML = html;
  tb.querySelectorAll("tr.row").forEach(function (el) {
    el.onclick = function () { showDetail(+el.getAttribute("data-id")); };
  });
}
function showList() {
  VIEW = "list";
  document.getElementById("detail-view").style.display = "none";
  document.getElementById("list-view").style.display = "block";
  renderCards(); renderList();
}

function resultHtml(r) {
  if (!r) return "";
  if (r.folds && r.folds.length && r.folds[0].p !== undefined) {
    var h = '<table><tr><th>구간</th><th>net</th><th>p-value</th><th>통과</th></tr>';
    r.folds.forEach(function (f) {
      h += '<tr><td>' + esc(f.period || f.window_start) + '</td><td class="' + (f.net > 0 ? "go" : "nogo") + '">' +
        pct(f.net) + '</td><td>' + esc(f.p) + '</td><td>' + (f.passed ? "✅" : "❌") + '</td></tr>';
    });
    return h + '</table>';
  }
  return '<pre>' + esc(JSON.stringify(r, null, 1)) + '</pre>';
}

function showDetail(id) {
  var e = LOG.filter(function (x) { return x.id === id; })[0];
  if (!e) return;
  VIEW = "detail";
  document.getElementById("list-view").style.display = "none";
  var d = document.getElementById("detail-view");
  d.style.display = "block";
  var btns = "";
  (e.curves || []).forEach(function (c, i) {
    btns += '<span class="btn' + (i === 0 ? " on" : "") + '" data-k="' + esc(c.key) + '">' + esc(c.label) + '</span>';
  });
  var head = '<span class="back" id="back-btn">← 전체 목록</span>' +
    '<h2 style="margin:4px 0 10px;font-size:17px;">' + esc(e.idea) + ' <span class="' + vcls(e.verdict) + '">' +
    (ICON[e.verdict] || "") + " " + esc(e.verdict) + '</span></h2>' +
    '<div class="box"><b>가설</b> ' + esc(e.hypothesis) + '<br><b>방법</b> ' + esc(e.method) +
    '<br><b>이유</b> ' + esc(e.reason) + '</div>';
  var charts = "";
  if (btns) {
    charts = '<div>' + btns + '</div><div id="curve-info" class="small" style="margin-bottom:8px"></div>' +
      '<div class="charts"><div><canvas id="ch-eq"></canvas></div><div><canvas id="ch-fold"></canvas></div></div>' +
      '<div class="small" style="margin:8px 0 16px">누적 수익률 곡선은 OOS 5개 구간을 이어 붙인 것이라 구간 사이에는 ' +
      '실제로 약 6개월 공백이 있어요. momentum/reversal 단독 결과를 비율대로 섞은 근사치입니다.</div>';
  }
  d.innerHTML = head + charts + '<div class="box">' + resultHtml(e.result) + '</div>';
  document.getElementById("back-btn").onclick = showList;
  d.querySelectorAll(".btn").forEach(function (b) {
    b.onclick = function () { loadCurve(b.getAttribute("data-k"), b); };
  });
  if (e.curves && e.curves.length) loadCurve(e.curves[0].key, d.querySelector(".btn"));
}

function loadCurve(key, btn) {
  document.querySelectorAll("#detail-view .btn").forEach(function (b) { b.classList.remove("on"); });
  if (btn) btn.classList.add("on");
  fetch("/api/curve/" + encodeURIComponent(key)).then(function (res) {
    if (!res.ok) { document.getElementById("curve-info").textContent = "곡선 데이터를 불러오지 못했어요"; return null; }
    return res.json();
  }).then(function (c) {
    if (!c) return;
    document.getElementById("curve-info").textContent =
      c.label + " · 누적 " + pct(c.final) + " · Sharpe " + c.sharpe + " · 최대낙폭 " + pct(c.mdd);
    if (CH1) CH1.destroy();
    if (CH2) CH2.destroy();
    var tick = {ticks: {color: "#aaa"}, grid: {color: "#262626"}};
    CH1 = new Chart(document.getElementById("ch-eq"), {
      type: "line",
      data: {labels: c.curve.map(function (p) { return p[0]; }),
             datasets: [{label: "누적 수익률(1.0=시작)", data: c.curve.map(function (p) { return p[1]; }),
                         borderColor: "#3b82f6", pointRadius: 0, borderWidth: 1.6}]},
      options: {plugins: {legend: {labels: {color: "#ccc"}}},
                scales: {x: {ticks: {color: "#aaa", maxTicksLimit: 8}, grid: {color: "#262626"}}, y: tick}}
    });
    CH2 = new Chart(document.getElementById("ch-fold"), {
      type: "bar",
      data: {labels: c.folds.map(function (f) { return f.label; }),
             datasets: [{label: "구간별 수익률(%)", data: c.folds.map(function (f) { return +(f.net * 100).toFixed(1); }),
                         backgroundColor: c.folds.map(function (f) { return f.net >= 0 ? "#4ade80" : "#f87171"; })}]},
      options: {plugins: {legend: {labels: {color: "#ccc"}}}, scales: {x: tick, y: tick}}
    });
  });
}

function loadLog() {
  fetch("/api/log").then(function (r) { return r.json(); }).then(function (d) {
    LOG = d;
    renderCards();
    if (VIEW === "list") renderList();
  });
}
function loadRequests() {
  fetch("/api/requests").then(function (r) { return r.json(); }).then(function (data) {
    var h = "";
    data.slice().reverse().forEach(function (r) {
      h += '<div class="req">' + esc(r.text) + '<br><span class="small">' + esc(r.status) + " · " + esc(r.ts) + '</span></div>';
    });
    document.getElementById("req-list").innerHTML = h;
  });
}
document.getElementById("submit-btn").onclick = function () {
  var t = document.getElementById("req-text").value.trim();
  if (!t) return;
  fetch("/api/submit", {method: "POST", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({text: t})}).then(function () {
    document.getElementById("req-text").value = "";
    loadRequests();
  });
};
loadLog(); loadRequests();
setInterval(function () { loadLog(); loadRequests(); }, 15000);

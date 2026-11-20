"""Build a self-contained, dependency-free HTML prototype.

The file can be opened directly from disk or served with
``python -m http.server 8000``. It embeds the demo outputs, so it never
fetches the confidential input pack.
"""

from __future__ import annotations

import json
from pathlib import Path


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kuku Promo Discovery — Demo Prototype</title>
<style>
  :root {
    --bg: #0c0f14; --panel: #151a23; --panel2: #1c2330; --line: #2a3445;
    --text: #e8edf5; --muted: #94a3b8; --accent: #7dd3fc; --good: #34d399;
    --weak: #fbbf24; --bad: #fb7185;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
         background: var(--bg); color: var(--text); }
  header { padding: 22px 28px; border-bottom: 1px solid var(--line);
           background: linear-gradient(120deg, #101827, #0c0f14); }
  h1 { margin: 0 0 6px; font-size: 24px; letter-spacing: -.02em; }
  h2 { margin: 0 0 12px; font-size: 17px; }
  h3 { margin: 0 0 8px; font-size: 14px; color: var(--muted); text-transform: uppercase;
       letter-spacing: .08em; }
  .sub { color: var(--muted); max-width: 900px; }
  .tag { display: inline-block; padding: 2px 8px; border: 1px solid var(--line);
         border-radius: 999px; font-size: 12px; color: var(--accent); margin-top: 8px; }
  main { padding: 22px 28px 48px; max-width: 1500px; margin: 0 auto; }
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
             gap: 12px; margin-bottom: 22px; }
  .metric { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
            padding: 14px; }
  .metric b { display: block; font-size: 26px; margin-top: 4px; }
  .metric span { color: var(--muted); font-size: 12px; text-transform: uppercase;
                 letter-spacing: .06em; }
  .layout { display: grid; grid-template-columns: minmax(320px, 440px) 1fr; gap: 18px; }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
           padding: 16px; }
  .filters { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
  select, input { width: 100%; padding: 9px 10px; border-radius: 8px; border: 1px solid var(--line);
                  background: var(--panel2); color: var(--text); }
  .list { max-height: 72vh; overflow: auto; display: flex; flex-direction: column; gap: 8px; }
  .card { text-align: left; width: 100%; cursor: pointer; border: 1px solid var(--line);
          background: var(--panel2); color: var(--text); border-radius: 10px; padding: 11px 12px; }
  .card:hover, .card.active { border-color: var(--accent); }
  .card .row { display: flex; justify-content: space-between; gap: 8px; align-items: baseline; }
  .card .title { font-weight: 650; font-size: 14px; }
  .card .meta { color: var(--muted); font-size: 12px; margin-top: 4px; }
  .score { font-variant-numeric: tabular-nums; font-weight: 700; }
  .pill { display: inline-block; border-radius: 999px; padding: 1px 8px; font-size: 11px;
          border: 1px solid currentColor; }
  .Good { color: var(--good); } .Weak { color: var(--weak); } .Bad, .Invalid { color: var(--bad); }
  .Needs { color: var(--accent); }
  .detail { min-height: 420px; }
  .detail-head { display: flex; justify-content: space-between; gap: 16px; align-items: start;
                 margin-bottom: 14px; }
  .quote { border-left: 3px solid var(--accent); padding: 8px 12px; margin: 8px 0 14px;
           background: #101722; border-radius: 0 8px 8px 0; }
  .quote small { color: var(--muted); display: block; margin-bottom: 4px; text-transform: uppercase;
                 letter-spacing: .06em; }
  .bars { display: grid; gap: 7px; margin: 12px 0 18px; }
  .bar { display: grid; grid-template-columns: 150px 1fr 44px; gap: 10px; align-items: center;
         font-size: 13px; }
  .track { height: 8px; border-radius: 99px; background: #0b1018; overflow: hidden; }
  .fill { height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--line);
           vertical-align: top; }
  th { color: var(--muted); font-weight: 600; font-size: 11px; text-transform: uppercase;
       letter-spacing: .06em; }
  .timeline { max-height: 330px; overflow: auto; }
  .notice { border: 1px solid #1e3a5f; background: #0e1a2b; color: #bae6fd; padding: 12px 14px;
            border-radius: 10px; margin: 14px 0 0; }
  .badpick { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px;
             margin-bottom: 8px; background: var(--panel2); }
  .badpick b { color: var(--bad); }
  .muted { color: var(--muted); }
  @media (max-width: 980px) { .layout { grid-template-columns: 1fr; } .list { max-height: 45vh; } }
</style>
</head>
<body>
<header>
  <h1>Kuku Promo Discovery</h1>
  <div class="sub">
    A working, read-only prototype of the candidate generator, explainable
    scorer and human-triage UI. This page uses <b>synthetic demo episodes</b>,
    not the confidential Kuku input pack.
  </div>
  <div class="tag">Ranked promos · source-segment timestamps · quality check</div>
</header>
<main>
  <div class="metrics" id="metrics"></div>

  <section class="panel" style="margin-bottom:18px">
    <h2>How to read this prototype</h2>
    <div class="muted">
      Every card is a 20–60s candidate. The score is an explainable heuristic,
      not measured ad performance. The detail panel shows the exact source
      segments and timestamps behind the clip. The quality-check section below
      names where the ranker still picks badly.
    </div>
  </section>

  <div class="layout">
    <section class="panel">
      <h2>Candidates</h2>
      <div class="filters">
        <select id="episode"><option value="all">All episodes</option></select>
        <select id="label">
          <option value="all">All labels</option>
          <option>Good Promo</option><option>Weak Promo</option>
          <option>Bad Promo</option><option>Needs Review</option>
        </select>
      </div>
      <input id="search" placeholder="Search hook, title, dialogue…">
      <div class="list" id="list" style="margin-top:10px"></div>
    </section>

    <section class="panel detail" id="detail"></section>
  </div>

  <section class="panel" style="margin-top:18px">
    <h2>Quality check — where it still picks badly</h2>
    <div id="quality"></div>
  </section>

  <div class="notice">
    Demo data is synthetic. Real-pack outputs are in <code>raw_outputs/</code>
    and are intended for the evaluator, not for public publication.
  </div>
</main>
<script>
const DATA = __DATA__;
const QUALITY = __QUALITY__;
const SUMMARY = __SUMMARY__;
const AUDIT = __AUDIT__;

const labelClass = (label) => String(label || "").split(" ")[0];
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
}[c]));

const scores = (c) => c.score_breakdown || {};
let activeId = DATA.length ? DATA[0].promo_id : null;

function metrics() {
  const labels = QUALITY.label_counts || {};
  const items = [
    ["Ranked promos", DATA.length],
    ["Episodes", new Set(DATA.map(c => c.episode_number)).size],
    ["Good / Weak / Bad",
      `${labels["Good Promo"] || 0} / ${labels["Weak Promo"] || 0} / ${labels["Bad Promo"] || 0}`],
    ["Duplicates removed", QUALITY.duplicates_removed ?? 0],
    ["Mid-dialogue cuts", QUALITY.clips_ending_mid_dialogue ?? 0],
    ["Brief checks", `${AUDIT.passed_checks ?? 0}/${AUDIT.total_checks ?? 0}`],
    ["Score range", `${QUALITY.score_min ?? 0}\u2013${QUALITY.score_max ?? 0}`],
  ];
  document.getElementById("metrics").innerHTML = items.map(([k,v]) =>
    `<div class="metric"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
}

function fillEpisodes() {
  const select = document.getElementById("episode");
  [...new Set(DATA.map(c => c.episode_number))].sort((a,b) => a-b).forEach(n => {
    const option = document.createElement("option");
    option.value = n; option.textContent = `Episode ${n}`;
    select.appendChild(option);
  });
}

function filtered() {
  const episode = document.getElementById("episode").value;
  const label = document.getElementById("label").value;
  const search = document.getElementById("search").value.toLowerCase().trim();
  return DATA.filter(c => {
    if (episode !== "all" && String(c.episode_number) !== episode) return false;
    if (label !== "all" && c.human_review_label !== label) return false;
    if (search) {
      const hay = [c.title, c.opening_hook, c.ending_cliffhanger_or_payoff,
                   (c.dialogue || []).join(" "), c.why_it_works].join(" ").toLowerCase();
      if (!hay.includes(search)) return false;
    }
    return true;
  });
}

function renderList() {
  const list = document.getElementById("list");
  const rows = filtered();
  if (!rows.length) {
    list.innerHTML = `<div class="muted">No candidates match these filters.</div>`;
    return;
  }
  list.innerHTML = rows.map(c => {
    const s = scores(c);
    return `<button class="card ${c.promo_id === activeId ? "active" : ""}" data-id="${esc(c.promo_id)}">
      <div class="row"><span class="title">#${esc(c.rank)} · Ep ${esc(c.episode_number)} · ${esc(c.title)}</span>
      <span class="score">${esc(s.final_score)}</span></div>
      <div class="meta">${esc(c.start_timestamp)}–${esc(c.end_timestamp)} ·
      ${esc(c.duration_seconds)}s ·
      <span class="pill ${labelClass(c.human_review_label)}">${esc(c.human_review_label)}</span></div>
      <div class="meta">${esc((c.opening_hook || "").slice(0, 105))}</div>
    </button>`;
  }).join("");
  list.querySelectorAll(".card").forEach(button => {
    button.onclick = () => { activeId = button.dataset.id; renderList(); renderDetail(); };
  });
}

function renderDetail() {
  const c = DATA.find(item => item.promo_id === activeId) || DATA[0];
  const detail = document.getElementById("detail");
  if (!c) { detail.innerHTML = "<p>No data.</p>"; return; }
  const s = scores(c);
  const dimensions = [
    ["Hook strength", s.hook_strength], ["Emotional impact", s.emotional_impact],
    ["Suspense / curiosity", s.suspense_curiosity],
    ["Cliffhanger / payoff", s.cliffhanger_payoff],
    ["Standalone clarity", s.standalone_clarity],
    ["Promotional relevance", s.promotional_relevance],
  ];
  const segments = (c.source_segments || []).map(segment => `<tr>
    <td>${esc(segment.segment_type)}</td><td>${esc(segment.speaker || "")}</td>
    <td>${esc(segment.start_timestamp)}–${esc(segment.end_timestamp)}</td>
    <td>${esc(segment.content)}</td></tr>`).join("");

  detail.innerHTML = `
    <div class="detail-head">
      <div><h2>${esc(c.title)}</h2>
        <div class="muted">Rank #${esc(c.rank)} · Episode ${esc(c.episode_number)} ·
        ${esc(c.start_timestamp)}–${esc(c.end_timestamp)} · ${esc(c.duration_seconds)}s</div></div>
      <div style="text-align:right"><div class="score" style="font-size:30px">${esc(s.final_score)}</div>
        <span class="pill ${labelClass(c.human_review_label)}">${esc(c.human_review_label)}</span></div>
    </div>
    <div class="quote"><small>Opening hook</small>${esc(c.opening_hook)}</div>
    <div class="quote"><small>Main dramatic moment</small>${esc(c.main_dramatic_moment)}</div>
    <div class="quote"><small>Ending / cliffhanger</small>${esc(c.ending_cliffhanger_or_payoff)}</div>
    <p><b>Why it works:</b> ${esc(c.why_it_works || c.promotional_justification)}</p>
    <p class="muted">${esc(c.rank_reason || "")}</p>
    <h3>Score breakdown</h3>
    <div class="bars">${dimensions.map(([name, value]) => `
      <div class="bar"><span>${esc(name)}</span>
      <div class="track"><div class="fill" style="width:${Math.max(0, Math.min(100, Number(value || 0) * 10))}%"></div></div>
      <span>${esc(value)}</span></div>`).join("")}</div>
    <h3>Source segments (ordered)</h3>
    <div class="timeline"><table><thead><tr><th>Type</th><th>Speaker</th><th>Start–End</th><th>Content</th></tr></thead>
    <tbody>${segments}</tbody></table></div>
    <p class="muted" style="margin-top:12px">Analysis: ${esc(c.analysis_mode)} · score source:
    ${esc(c.score_source)} · validation: ${esc(c.validation_status)}</p>`;
}

function renderQuality() {
  const quality = document.getElementById("quality");
  const bad = QUALITY.bad_pick_examples || [];
  const rows = [
    ["Clips ending mid-dialogue", QUALITY.clips_ending_mid_dialogue],
    ["Clips crossing scene boundaries", QUALITY.clips_crossing_scene_boundaries],
    ["Hooks of two words or fewer", QUALITY.hooks_two_words_or_less],
    ["Hooks starting after 3 seconds", QUALITY.hooks_beyond_3_seconds],
    ["Closure endings", QUALITY.closure_endings],
    ["Distinct durations", QUALITY.duration_distinct_values],
  ];
  const auditNote = AUDIT.status ? `<p><b>Hard brief requirements: ${esc(AUDIT.status)}</b>
    \u2014 ${esc(AUDIT.passed_checks)}/${esc(AUDIT.total_checks)} passed. These are
    admissibility checks (duration, coverage, hooks, timestamps, source
    segments, labels, ranking), not quality judgements.</p>` : "";
  quality.innerHTML = `${auditNote}<table><tbody>${rows.map(([k,v]) =>
    `<tr><td>${esc(k)}</td><td><b>${esc(v)}</b></td></tr>`).join("")}</tbody></table>
    <h3 style="margin-top:16px">Bad-pick examples</h3>
    ${bad.length ? bad.map(item => `<div class="badpick"><b>Rank ${esc(item.rank)} ·
    ${esc(item.promo_id)}</b> — score ${esc(item.score)}, ${esc(item.label)}
    <div class="muted">${esc(item.why_it_fails)}</div></div>`).join("") :
    `<div class="muted">No candidate fell below the weak threshold in this run.
    That is not proof of quality; it means the scorer needs a harder gold set.</div>`}`;
}

metrics(); fillEpisodes(); renderList(); renderDetail(); renderQuality();
document.getElementById("episode").onchange = renderList;
document.getElementById("label").onchange = renderList;
document.getElementById("search").oninput = renderList;
</script>
</body>
</html>
"""


def build_static_prototype(export_dir, output_path):
    export_dir = Path(export_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads((export_dir / "ranked_promos.json").read_text(encoding="utf-8"))
    quality = json.loads((export_dir / "quality_check.json").read_text(encoding="utf-8"))
    summary = json.loads((export_dir / "batch4_summary.json").read_text(encoding="utf-8"))
    audit_path = export_dir / "requirements_check.json"
    audit = (
        json.loads(audit_path.read_text(encoding="utf-8"))
        if audit_path.exists()
        else {}
    )

    def safe_json(value):
        return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

    html = (
        TEMPLATE
        .replace("__DATA__", safe_json(data))
        .replace("__QUALITY__", safe_json(quality))
        .replace("__SUMMARY__", safe_json(summary))
        .replace("__AUDIT__", safe_json(audit))
    )
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)

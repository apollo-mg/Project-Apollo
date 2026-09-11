#!/usr/bin/env python3
"""Build the shareable "Pelican Judging Panel" page for outside raters.

Same 32 renders, same random codes and same 75 pairs in the same order as Mark's page, read from the
sealed mapping, so every rater's picks line up with his. The differences are deliberate:
- No Claude storage. Progress lives in the rater's own browser, and results leave the page only when
  the rater copies them and sends them to Mark. The page declares no capabilities, so it can be
  shared publicly.
- Each rater gets their own random left/right flips, keyed on the unordered pair, so a repeat is
  always shown swapped relative to its original and the page never says which pairs repeat.
- A pick is recorded as the winning drawing's code, not as left/right.
- The flag asks about exposure outside the page, because an outside rater cannot know which quant
  made a drawing.
Like Mark's page, it carries no labels.

Usage: build_share_page.py OUT.html
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_blind_page as B  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if not B.MAPPING.exists():
        sys.exit("no sealed mapping -- build Mark's page first")
    mp = json.loads(B.MAPPING.read_text())
    page = {"pairs": [{"id": p["id"], "a": p["pair"][0], "b": p["pair"][1]} for p in mp["pairs"]],
            "img": {c: B.data_uri(B.SRC / v["png"]) for c, v in mp["drawings"].items()}}
    out = Path(sys.argv[1])
    out.write_text(TEMPLATE.replace("/*DATA*/null", json.dumps(page, separators=(",", ":"))))
    print(f"page {out} ({out.stat().st_size / 1e6:.2f} MB), pairs {len(page['pairs'])}, drawings {len(page['img'])}")


TEMPLATE = r'''<title>Pelican Judging Panel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=Schibsted+Grotesk:wght@400;600;800&display=swap">
<style>
:root{
  --ground:#EDF1F2; --paper:#FFFFFF; --ink:#1D2A31; --ink-2:#56666E; --rule:#C7D1D5;
  --pouch:#B4581A; --on-pouch:#FFFFFF; --pouch-soft:#F7E6D6; --sea:#2F6F86;
  --sans:"Schibsted Grotesk","Segoe UI",system-ui,-apple-system,sans-serif;
  --type:"Courier Prime","Courier New",ui-monospace,monospace;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#11181C; --paper:#1A2429; --ink:#E4EBEE; --ink-2:#93A4AB; --rule:#2B3840;
    --pouch:#E7924A; --on-pouch:#1B1206; --pouch-soft:#3A2A1D; --sea:#7FB6C9;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --ground:#11181C; --paper:#1A2429; --ink:#E4EBEE; --ink-2:#93A4AB; --rule:#2B3840;
  --pouch:#E7924A; --on-pouch:#1B1206; --pouch-soft:#3A2A1D; --sea:#7FB6C9;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:16px/1.5 var(--sans)}
.wrap{max-width:1080px;margin:0 auto;padding-inline:clamp(16px,4vw,40px);padding-block:22px 36px;display:grid;gap:18px}
header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:6px 24px}
h1{margin:0;font-weight:800;font-size:clamp(1.35rem,2.6vw,1.8rem);letter-spacing:-0.02em;text-wrap:balance}
.count{font-family:var(--type);font-size:0.95rem;color:var(--ink-2);font-variant-numeric:tabular-nums}
.count b{color:var(--ink)}
.progress{height:3px;background:var(--rule);border-radius:2px;overflow:hidden;margin-top:-8px}
.progress i{display:block;height:100%;width:0;background:var(--pouch);transition:width .25s ease}
.intro{margin:0;max-width:66ch;color:var(--ink-2)}
.judge{display:grid;gap:16px}
.question{margin:0;font-size:clamp(1.1rem,2.2vw,1.35rem);font-weight:600;line-height:1.3;text-wrap:balance}
.question small{display:block;margin-top:4px;font-size:0.9rem;font-weight:400;color:var(--ink-2)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:clamp(12px,2.5vw,28px)}
.card{appearance:none;border:0;margin:0;padding:0;background:none;color:inherit;font:inherit;text-align:left;cursor:pointer;display:grid;gap:8px}
.frame{display:block;background:var(--paper);border:1px solid var(--rule);border-radius:3px;padding:10px;transition:border-color .12s,box-shadow .12s,background-color .12s}
.frame img{display:block;width:100%;max-width:100%;height:auto;aspect-ratio:4/3;border:1px solid var(--rule)}
.tag{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding-inline:2px;font-family:var(--type);font-size:0.9rem;color:var(--ink-2)}
.code{color:var(--ink);font-weight:700;letter-spacing:0.08em}
.card:hover .frame{border-color:var(--pouch)}
.card:focus-visible{outline:none}
.card:focus-visible .frame{box-shadow:0 0 0 3px var(--sea)}
.card.chosen .frame{border-color:var(--pouch);background:var(--pouch-soft);box-shadow:0 0 0 2px var(--pouch)}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px 20px}
.btn{font:600 0.95rem/1 var(--sans);padding:11px 16px;border-radius:3px;border:1px solid var(--ink-2);background:transparent;color:var(--ink);cursor:pointer}
.btn:hover{border-color:var(--ink)}
.btn.chosen,.btn.primary{background:var(--pouch);border-color:var(--pouch);color:var(--on-pouch)}
.toggle{display:inline-flex;align-items:center;gap:8px;font-size:0.95rem;cursor:pointer}
.toggle input{width:18px;height:18px;margin:0;accent-color:var(--pouch)}
.link{font:inherit;font-size:inherit;padding:0;border:0;background:none;color:var(--ink-2);text-decoration:underline;text-underline-offset:3px;cursor:pointer}
.link[disabled]{opacity:.4;cursor:default}
.btn:focus-visible,.link:focus-visible,.toggle input:focus-visible,.field:focus-visible{outline:3px solid var(--sea);outline-offset:2px}
.prevpick{font-family:var(--type);font-size:0.9rem;color:var(--ink-2)}
.keys{margin:0;font-family:var(--type);font-size:0.85rem;color:var(--ink-2)}
@media (hover:none){.keys{display:none}}
.status{min-height:1.5em;font-size:0.9rem;color:var(--ink-2)}
.status.warn{color:var(--ink);font-weight:600}
.done{display:grid;gap:12px;padding:24px;background:var(--paper);border:1px solid var(--rule);border-radius:3px}
.done h2{margin:0;font-size:1.3rem;text-wrap:balance}
.done p{margin:0;max-width:62ch}
.lbl{font-weight:600;font-size:0.95rem}
.field{font:inherit;padding:9px 10px;border:1px solid var(--ink-2);border-radius:3px;background:var(--ground);color:var(--ink);width:100%;max-width:22rem}
textarea.field{max-width:none;min-height:9rem;font:0.85rem/1.45 var(--type);resize:vertical}
footer{padding-block:12px 0;border-top:1px solid var(--rule);font-size:0.85rem;color:var(--ink-2)}
footer p{margin:0;max-width:72ch}
/* after the base rules it overrides -- equal specificity, so order decides */
@media (max-width:520px){
  .wrap{gap:12px}
  .pair{grid-template-columns:1fr;gap:10px}
  .frame{padding:6px}
  .frame img{width:auto;height:auto;max-height:30vh;margin-inline:auto}
}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>

<div class="wrap">
  <header>
    <h1>Pelican Judging Panel</h1>
    <div class="count">Pair <b id="n">1</b> of <span id="total">75</span> &middot; <span id="judged">0</span> judged</div>
  </header>
  <div class="progress" aria-hidden="true"><i id="bar"></i></div>
  <p class="intro">Thirty-two drawings of a pelican riding a bicycle, all made by an AI model. You'll see two at a time: pick the better picture. There are 75 pairs, about 10&ndash;15 minutes, and your progress is saved in this browser. When you finish, copy your results and send them to Mark.</p>

  <main class="judge" id="judge">
    <p class="question">Which is the better picture of a pelican riding a bicycle?
      <small>Judge each picture as a whole. Some pairs are close; "Too close to call" is a real answer.</small></p>
    <div class="pair">
      <button class="card" id="cardA" type="button" aria-label="Choose drawing A">
        <span class="frame"><img id="imgA" alt="Drawing A" width="512" height="384"></span>
        <span class="tag"><span>A &middot; <span class="code" id="codeA"></span></span><span class="keys">press 1</span></span>
      </button>
      <button class="card" id="cardB" type="button" aria-label="Choose drawing B">
        <span class="frame"><img id="imgB" alt="Drawing B" width="512" height="384"></span>
        <span class="tag"><span>B &middot; <span class="code" id="codeB"></span></span><span class="keys">press 2</span></span>
      </button>
    </div>
    <div class="controls">
      <button class="btn" id="tie" type="button">Too close to call</button>
      <label class="toggle" for="seen"><input type="checkbox" id="seen"><span>I've seen one of these outside this page</span></label>
      <button class="link" id="back" type="button">Back one pair</button>
      <span class="prevpick" id="prev"></span>
    </div>
    <p class="keys">Keys: 1 or &larr; picks A &middot; 2 or &rarr; picks B &middot; T too close &middot; S seen outside &middot; U back</p>
    <div class="status" id="status" role="status" aria-live="polite"></div>
  </main>

  <section class="done" id="done" hidden>
    <h2 id="doneTitle">All pairs judged. Thank you.</h2>
    <p id="doneText"></p>
    <label class="lbl" for="handle">Your name or Discord handle</label>
    <input class="field" type="text" id="handle" maxlength="40" autocomplete="nickname">
    <label class="lbl" for="result">Your results</label>
    <textarea class="field" id="result" readonly></textarea>
    <div class="controls">
      <button class="btn primary" id="copy" type="button">Copy results</button>
      <span class="prevpick" id="copied" role="status" aria-live="polite"></span>
    </div>
    <p>Send them to Mark in a direct message, not in the channel, so the other judges stay unbiased.</p>
    <p><button class="link" id="review" type="button">Go back and change a pick</button></p>
  </section>

  <footer><p>Each drawing is a 512&times;384 render tagged with a random code. Your progress is kept in this browser only, and nothing is sent anywhere until you copy your results yourself. <button class="link" id="partial" type="button">Copy results so far</button></p></footer>
</div>

<script>
(function () {
  const DATA = /*DATA*/null;
  const PAIRS = DATA.pairs, IMG = DATA.img, TOTAL = PAIRS.length;
  const $ = (id) => document.getElementById(id);
  const reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const KEY = "pelican-panel-v1";
  const NOT_KEPT = "This browser isn't keeping your progress. Finish in one sitting, or copy your results before you close the page.";
  let st = null, stored = true, idx = 0, shownAt = 0, busy = false, exporting = false;

  function fresh() {
    const a = new Uint32Array(2);
    try { crypto.getRandomValues(a); } catch (e) { a[0] = Math.random() * 4294967296; a[1] = Math.random() * 4294967296; }
    return { v: 1, seed: a[0].toString(36) + a[1].toString(36), picks: {}, handle: "" };
  }
  function load() {
    try { const s = JSON.parse(localStorage.getItem(KEY) || "null"); if (s && s.seed && s.picks) return s; } catch (e) {}
    return fresh();
  }
  function persist() { try { localStorage.setItem(KEY, JSON.stringify(st)); stored = true; } catch (e) { stored = false; } }
  function fnv(s) { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); } return h >>> 0; }
  // Sides per rater, keyed on the unordered pair: a repeat always appears swapped relative to its original.
  function sides(p) { const k = p.a < p.b ? p.a + p.b : p.b + p.a; return (fnv(st.seed + k) & 1) ? [p.b, p.a] : [p.a, p.b]; }
  function doneCount() { let n = 0; for (const p of PAIRS) if (st.picks[p.id]) n++; return n; }
  function nextOpen(after) {
    for (let i = after + 1; i < TOTAL; i++) if (!st.picks[PAIRS[i].id]) return i;
    for (let i = 0; i < TOTAL; i++) if (!st.picks[PAIRS[i].id]) return i;
    return -1;
  }
  function setStatus(text, warn) { const s = $("status"); s.textContent = text || ""; s.classList.toggle("warn", !!warn); }

  function resultText() {
    const ms = Object.values(st.picks).map(function (r) { return r.ms; }).filter(function (x) { return typeof x === "number"; }).sort(function (a, b) { return a - b; });
    const med = ms.length ? (ms[(ms.length - 1) >> 1] + ms[ms.length >> 1]) / 2 : 0;
    const who = (st.handle || "").replace(/[|\r\n]/g, " ").trim() || "anonymous";
    const body = PAIRS.filter(function (p) { return st.picks[p.id]; })
      .map(function (p) { const r = st.picks[p.id]; return p.id + ":" + r.w + (r.f ? "*" : ""); }).join(" ");
    return "PELICAN-PANEL v1 | " + who + " | seed " + st.seed + " | " + doneCount() + "/" + TOTAL +
           " | median " + (med / 1000).toFixed(1) + "s\n" + body;
  }

  function showExport(n) {
    $("judge").hidden = true; $("done").hidden = false;
    const complete = n === TOTAL;
    $("doneTitle").textContent = complete ? "All pairs judged. Thank you." : "Results so far: " + n + " of " + TOTAL + " pairs.";
    let ties = 0, flagged = 0;
    for (const id in st.picks) { const r = st.picks[id]; if (r.w === "=") ties++; if (r.f) flagged++; }
    $("doneText").textContent = ties + " called too close to call, " + flagged + " flagged as seen outside this page.";
    $("handle").value = st.handle || "";
    $("result").value = resultText();
    $("copied").textContent = "";
    $("review").textContent = complete ? "Go back and change a pick" : "Back to judging";
  }

  function render() {
    const n = doneCount();
    $("bar").style.width = (100 * n / TOTAL).toFixed(1) + "%";
    $("judged").textContent = n;
    $("total").textContent = TOTAL;
    if (exporting || idx < 0) { if (idx < 0) $("n").textContent = TOTAL; showExport(n); return; }
    $("judge").hidden = false; $("done").hidden = true;
    const p = PAIRS[idx], s = sides(p), prev = st.picks[p.id];
    $("n").textContent = idx + 1;
    $("imgA").src = IMG[s[0]]; $("imgB").src = IMG[s[1]];
    $("codeA").textContent = s[0]; $("codeB").textContent = s[1];
    $("cardA").classList.toggle("chosen", !!prev && prev.w === s[0]);
    $("cardB").classList.toggle("chosen", !!prev && prev.w === s[1]);
    $("tie").classList.toggle("chosen", !!prev && prev.w === "=");
    $("seen").checked = !!(prev && prev.f);
    $("back").disabled = idx === 0;
    $("prev").textContent = !prev ? "" : prev.w === "=" ? "Your pick: too close to call" : "Your pick: " + (prev.w === s[0] ? "A" : "B");
    shownAt = performance.now();
  }

  function choose(which) {
    if (busy || exporting || idx < 0) return;
    busy = true;
    const p = PAIRS[idx], s = sides(p);
    const w = which === "A" ? s[0] : which === "B" ? s[1] : "=";
    st.picks[p.id] = { w: w, f: $("seen").checked, ms: Math.round(performance.now() - shownAt) };
    persist();
    $("cardA").classList.toggle("chosen", which === "A");
    $("cardB").classList.toggle("chosen", which === "B");
    $("tie").classList.toggle("chosen", which === "=");
    setStatus(stored ? "" : NOT_KEPT, !stored);
    setTimeout(function () { idx = nextOpen(idx); busy = false; render(); }, reduced ? 0 : 180);
  }
  function back() {
    if (busy) return;
    exporting = false;
    if (idx < 0) idx = TOTAL - 1; else if (idx > 0) idx -= 1; else return;
    render();
  }

  $("cardA").addEventListener("click", function () { choose("A"); });
  $("cardB").addEventListener("click", function () { choose("B"); });
  $("tie").addEventListener("click", function () { choose("="); });
  $("back").addEventListener("click", back);
  $("review").addEventListener("click", function () { exporting = false; if (idx < 0) idx = TOTAL - 1; render(); });
  $("partial").addEventListener("click", function () { exporting = true; render(); $("done").scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" }); });
  $("handle").addEventListener("input", function () { st.handle = $("handle").value; persist(); $("result").value = resultText(); });
  $("copy").addEventListener("click", async function () {
    const t = resultText(); $("result").value = t;
    let ok = false;
    try { await navigator.clipboard.writeText(t); ok = true; } catch (e) {}
    if (!ok) { const ta = $("result"); ta.focus(); ta.select(); try { ok = document.execCommand("copy"); } catch (e) {} }
    $("copied").textContent = ok ? "Copied." : "Select the text above and copy it.";
  });
  document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
    const t = e.target;
    if (t && (t.tagName === "TEXTAREA" || (t.tagName === "INPUT" && t.type === "text"))) return;
    if (exporting || idx < 0) return;
    const k = e.key.toLowerCase();
    if (k === "1" || k === "arrowleft") { e.preventDefault(); choose("A"); }
    else if (k === "2" || k === "arrowright") { e.preventDefault(); choose("B"); }
    else if (k === "t" || k === "3") { e.preventDefault(); choose("="); }
    else if (k === "s") { e.preventDefault(); $("seen").checked = !$("seen").checked; }
    else if (k === "u" || k === "backspace") { e.preventDefault(); back(); }
  });

  st = load(); persist();
  idx = nextOpen(-1);
  render();
  if (!stored) setStatus(NOT_KEPT, true);
})();
</script>
'''

if __name__ == "__main__":
    main()

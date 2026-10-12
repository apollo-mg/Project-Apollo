#!/usr/bin/env python3
"""Build the blind pairwise page for the Turbo-Brilliance pelican test (PREREG_TURBOBRILLIANCE_PELICAN.md).

Pairs are fixed by design: MODE_rk vs CTRL_rk for CODER, QUINN and OMNI, k = 1..5. A pair whose mode side has no
drawing (a capped rep) is not shown; the prereg scores it as a CTRL win. The page carries no labels and, unlike the
ladder page, no drawing codes either: each CTRL drawing recurs, and a visible code would mark it. The only map from
the page to the arms is MAPPING_SEALED.json, which stays out of git until rating is done; its sha256 is committed in
an addendum first. Pair order and sides are drawn once from the OS RNG; a CTRL drawing never recurs within MIN_GAP
pairs. Later builds reuse the sealed mapping.

Usage: build_tb_blind_page.py OUT.html
"""
import base64, datetime, hashlib, io, json, random, sys
from pathlib import Path
from PIL import Image

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
SRC = ROOT / "data/receipts/svgbench-turbobrilliance"
MAPPING = SRC / "MAPPING_SEALED.json"
MODES, REPS, MIN_GAP = ("CODER", "QUINN", "OMNI"), range(1, 6), 3
ALPHABET = "ACDEFHJKLMNPRTUVWXY3479"


def make_mapping():
    rng = random.SystemRandom()
    have = {(a, k) for a in ("CTRL",) + MODES for k in REPS if (SRC / f"{a}_r{k}_p1.png").exists()}
    codes, draw = set(), {}
    for a, k in sorted(have):
        c = "".join(rng.choice(ALPHABET) for _ in range(5))
        while c in codes:
            c = "".join(rng.choice(ALPHABET) for _ in range(5))
        codes.add(c)
        draw[c] = {"arm": a, "rep": k, "png": f"{a}_r{k}_p1.png"}
    key = {(v["arm"], v["rep"]): c for c, v in draw.items()}
    shown, unshown = [], []
    for m in MODES:
        for k in REPS:
            if (m, k) in have and ("CTRL", k) in have:
                pair = [key[(m, k)], key[("CTRL", k)]]
                rng.shuffle(pair)
                shown.append({"mode": m, "rep": k, "pair": pair})
            else:
                unshown.append({"mode": m, "rep": k, "missing": [a for a in (m, "CTRL") if (a, k) not in have]})
    for _ in range(100000):                       # rejection-sample an order with CTRL repeats spaced apart
        rng.shuffle(shown)
        last, ok = {}, True
        for i, p in enumerate(shown):
            ctrl = key[("CTRL", p["rep"])]
            if ctrl in last and i - last[ctrl] <= MIN_GAP:
                ok = False
                break
            last[ctrl] = i
        if ok:
            break
    else:
        sys.exit("no order satisfies MIN_GAP")
    for i, p in enumerate(shown, 1):
        p["id"] = f"p{i:02d}"
    return {"built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "min_gap": MIN_GAP, "drawings": draw, "pairs": shown, "unshown": unshown}


def data_uri(png):
    im = Image.open(png).convert("RGBA")
    flat = Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("RGB")
    buf = io.BytesIO()
    flat.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    if MAPPING.exists():
        mp = json.loads(MAPPING.read_text())
        print(f"reusing sealed mapping ({MAPPING.name})")
    else:
        mp = make_mapping()
        MAPPING.write_text(json.dumps(mp, indent=1, sort_keys=True) + "\n")
        print(f"NEW mapping written: {MAPPING}")
    page = {"pairs": [{"id": p["id"], "a": p["pair"][0], "b": p["pair"][1]} for p in mp["pairs"]],
            "img": {c: data_uri(SRC / v["png"]) for c, v in mp["drawings"].items()}}
    out.write_text(TEMPLATE.replace("/*DATA*/null", json.dumps(page, separators=(",", ":"))))
    print(f"drawings {len(mp['drawings'])}  shown pairs {len(mp['pairs'])}  unshown {len(mp['unshown'])}")
    print(f"page {out} ({out.stat().st_size / 1e6:.2f} MB)")
    print(f"MAPPING_SEALED.json sha256 {hashlib.sha256(MAPPING.read_bytes()).hexdigest()}")


TEMPLATE = r'''<title>Blind Pelican Pairs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=Schibsted+Grotesk:wght@400;600;800&display=swap">
<style>
/* layout: one pair at a time, two framed renders side by side (stacked on phones), two questions under them */
:root{
  --ground:#EDF1F2; --paper:#FFFFFF; --ink:#1D2A31; --ink-2:#56666E; --rule:#C7D1D5;
  --pouch:#B4581A; --on-pouch:#FFFFFF; --pouch-soft:#F7E6D6; --sea:#2F6F86; --sea-soft:#DCEBF0;
  --sans:"Schibsted Grotesk","Segoe UI",system-ui,-apple-system,sans-serif;
  --type:"Courier Prime","Courier New",ui-monospace,monospace;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#11181C; --paper:#1A2429; --ink:#E4EBEE; --ink-2:#93A4AB; --rule:#2B3840;
    --pouch:#E7924A; --on-pouch:#1B1206; --pouch-soft:#3A2A1D; --sea:#7FB6C9; --sea-soft:#1C3440;
    color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --ground:#11181C; --paper:#1A2429; --ink:#E4EBEE; --ink-2:#93A4AB; --rule:#2B3840;
  --pouch:#E7924A; --on-pouch:#1B1206; --pouch-soft:#3A2A1D; --sea:#7FB6C9; --sea-soft:#1C3440;
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
.judge{display:grid;gap:16px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:clamp(12px,2.5vw,28px)}
.card{appearance:none;border:0;margin:0;padding:0;background:none;color:inherit;font:inherit;text-align:left;cursor:pointer;display:grid;gap:8px;min-width:0}
.frame{display:block;background:var(--paper);border:1px solid var(--rule);border-radius:3px;padding:10px;transition:border-color .12s,box-shadow .12s,background-color .12s}
.frame img{display:block;width:100%;max-width:100%;height:auto;aspect-ratio:4/3;border:1px solid var(--rule)}
.tag{padding-inline:2px;font-family:var(--type);font-size:0.95rem;font-weight:700;letter-spacing:0.08em}
.card:hover:not([disabled]) .frame{border-color:var(--pouch)}
.card:focus-visible{outline:none}
.card:focus-visible .frame{box-shadow:0 0 0 3px var(--sea)}
.card.chosen .frame{border-color:var(--pouch);background:var(--pouch-soft);box-shadow:0 0 0 2px var(--pouch)}
.card.guessed .frame{outline:3px dashed var(--sea);outline-offset:3px}
.q{display:grid;gap:10px;padding:14px 16px;background:var(--paper);border:1px solid var(--rule);border-radius:3px}
.q.active{border-color:var(--ink-2)}
.q.off{opacity:.5}
.q h2{margin:0;font-size:clamp(1.02rem,2vw,1.2rem);font-weight:600;line-height:1.3;text-wrap:balance}
.q h2 small{display:block;margin-top:2px;font-size:0.88rem;font-weight:400;color:var(--ink-2)}
.opts{display:flex;flex-wrap:wrap;gap:8px 10px}
.btn{font:600 0.95rem/1 var(--sans);padding:11px 16px;border-radius:3px;border:1px solid var(--ink-2);background:transparent;color:var(--ink);cursor:pointer}
.btn:hover:not([disabled]){border-color:var(--ink)}
.btn.chosen{background:var(--pouch);border-color:var(--pouch);color:var(--on-pouch)}
.btn.g.chosen{background:var(--sea);border-color:var(--sea);color:var(--paper)}
.btn[disabled]{opacity:.45;cursor:default}
.btn kbd{font:700 0.8rem var(--type);margin-left:6px;opacity:.75}
@media (hover:none){.btn kbd,.keys{display:none}}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px 20px}
.link{font:inherit;font-size:0.95rem;padding:0;border:0;background:none;color:var(--ink-2);text-decoration:underline;text-underline-offset:3px;cursor:pointer}
.link[disabled]{opacity:.4;cursor:default}
.btn:focus-visible,.link:focus-visible{outline:3px solid var(--sea);outline-offset:2px}
.keys{margin:0;font-family:var(--type);font-size:0.85rem;color:var(--ink-2)}
.status{min-height:1.5em;font-size:0.9rem;color:var(--ink-2)}
.status.warn{color:var(--ink);font-weight:600}
.done{display:grid;gap:12px;padding:24px;background:var(--paper);border:1px solid var(--rule);border-radius:3px}
.done h2{margin:0;font-size:1.3rem;text-wrap:balance}
.done p{margin:0;max-width:62ch}
.export{display:grid;gap:8px}
.export textarea{width:100%;min-height:5.5em;font:0.85rem/1.4 var(--type);color:var(--ink);background:var(--ground);border:1px solid var(--rule);border-radius:3px;padding:8px;resize:vertical}
footer{padding-block:12px 0;border-top:1px solid var(--rule);font-size:0.85rem;color:var(--ink-2)}
footer p{margin:0;max-width:72ch}
@media (max-width:520px){
  .wrap{gap:12px}
  .pair{grid-template-columns:1fr;gap:10px}
  .frame{padding:6px}
  .frame img{width:auto;height:auto;max-height:28vh;margin-inline:auto}
}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>

<div class="wrap">
  <header>
    <h1>Blind Pelican Pairs</h1>
    <div class="count">Pair <b id="n">1</b> of <span id="total">13</span> &middot; <span id="judged">0</span> done</div>
  </header>
  <div class="progress" aria-hidden="true"><i id="bar"></i></div>

  <main class="judge" id="judge">
    <div class="pair">
      <button class="card" id="cardA" type="button" aria-label="Drawing A">
        <span class="frame"><img id="imgA" alt="Drawing A" width="512" height="384"></span>
        <span class="tag">A</span>
      </button>
      <button class="card" id="cardB" type="button" aria-label="Drawing B">
        <span class="frame"><img id="imgB" alt="Drawing B" width="512" height="384"></span>
        <span class="tag">B</span>
      </button>
    </div>

    <section class="q" id="q1">
      <h2>1. Which is the better picture of a pelican riding a bicycle?
        <small>Judge each picture as a whole. Both answered the same prompt.</small></h2>
      <div class="opts">
        <button class="btn" id="p_a" type="button">A<kbd>1</kbd></button>
        <button class="btn" id="p_b" type="button">B<kbd>2</kbd></button>
        <button class="btn" id="p_tie" type="button">Can't decide<kbd>3</kbd></button>
      </div>
    </section>

    <section class="q off" id="q2">
      <h2>2. One of these was made with a long persona prompt. Which one?
        <small>A guess is fine. Pick "No idea" if nothing tells you.</small></h2>
      <div class="opts">
        <button class="btn g" id="g_a" type="button" disabled>A<kbd>1</kbd></button>
        <button class="btn g" id="g_b" type="button" disabled>B<kbd>2</kbd></button>
        <button class="btn g" id="g_none" type="button" disabled>No idea<kbd>3</kbd></button>
      </div>
    </section>

    <div class="controls">
      <button class="link" id="back" type="button">Back one pair</button>
    </div>
    <p class="keys">Keys: 1, 2, 3 answer whichever question is highlighted &middot; U goes back one pair</p>
    <div class="status" id="status" role="status" aria-live="polite"></div>
  </main>

  <section class="done" id="done" hidden>
    <h2>All pairs done. Thank you.</h2>
    <p id="doneText"></p>
    <p id="savedNote"></p>
    <div class="export" id="exportBox" hidden>
      <p>Your answers could not be saved to the page. Copy this code and send it to whoever shared the page with you:</p>
      <textarea id="exportText" readonly aria-label="Your answers as a code"></textarea>
      <div><button class="btn" id="copy" type="button">Copy code</button> <span id="copyMsg" class="keys"></span></div>
    </div>
    <p><button class="link" id="review" type="button">Go back and change an answer</button></p>
  </section>

  <footer><p>Each drawing is the render the svgbench scorer saw, composited onto white. The page shows no labels or codes. Pair order and left/right sides were shuffled once when the page was built. Some drawings appear in more than one pair.</p></footer>
</div>

<script>
(function () {
  const DATA = /*DATA*/null;
  const PAIRS = DATA.pairs, IMG = DATA.img, TOTAL = PAIRS.length;
  const $ = (id) => document.getElementById(id);
  const reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const LS_KEY = "tb-pelican-pairs-v1";
  let picks = {}, idx = 0, shownAt = 0, ready = false, busy = false;
  let db = null, uid = null, store = false, rootMarked = false;
  let pref = null;                                  // preference for the pair on screen, before the guess
  const pending = new Map();

  function lsLoad() { try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}") || {}; } catch (e) { return {}; } }
  function lsSave() { try { localStorage.setItem(LS_KEY, JSON.stringify(picks)); } catch (e) {} }
  function setStatus(text, warn) { const s = $("status"); s.textContent = text || ""; s.classList.toggle("warn", !!warn); }
  function doneCount() { let n = 0; for (const p of PAIRS) if (picks[p.id]) n++; return n; }
  function nextOpen(after) {
    for (let i = after + 1; i < TOTAL; i++) if (!picks[PAIRS[i].id]) return i;
    for (let i = 0; i < TOTAL; i++) if (!picks[PAIRS[i].id]) return i;
    return -1;
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function once(fn) {
    try { return await fn(); }
    catch (e) { if (e && e.code === "unavailable") { await sleep(400 + Math.random() * 500); return fn(); } throw e; }
  }
  function exportCode() {
    const rows = PAIRS.filter((p) => picks[p.id]).map((p) => { const r = picks[p.id]; return [p.id, r.a, r.b, r.pref, r.guess, r.ms]; });
    return "TBP1:" + btoa(JSON.stringify(rows));
  }

  function paintQuestions() {
    const p = PAIRS[idx], prev = picks[p.id];
    const pv = pref || (prev && prev.pref), gv = prev && !pref ? prev.guess : null;
    for (const [id, v] of [["p_a", "a"], ["p_b", "b"], ["p_tie", "tie"]]) $(id).classList.toggle("chosen", pv === v);
    $("cardA").classList.toggle("chosen", pv === "a");
    $("cardB").classList.toggle("chosen", pv === "b");
    const q2on = !!pv;
    $("q1").classList.toggle("active", !q2on); $("q2").classList.toggle("active", q2on);
    $("q2").classList.toggle("off", !q2on);
    for (const [id, v] of [["g_a", "a"], ["g_b", "b"], ["g_none", "none"]]) {
      $(id).disabled = !q2on || !ready; $(id).classList.toggle("chosen", gv === v);
    }
    $("cardA").classList.toggle("guessed", gv === "a");
    $("cardB").classList.toggle("guessed", gv === "b");
  }

  function render() {
    const n = doneCount();
    $("bar").style.width = (100 * n / TOTAL).toFixed(1) + "%";
    $("judged").textContent = n; $("total").textContent = TOTAL;
    if (idx < 0) {
      $("judge").hidden = true; $("done").hidden = false; $("n").textContent = TOTAL;
      let ties = 0, none = 0;
      for (const p of PAIRS) { const r = picks[p.id]; if (!r) continue; if (r.pref === "tie") ties++; if (r.guess === "none") none++; }
      $("doneText").textContent = ties + " called can't decide, " + none + " persona guesses left as no idea.";
      const saved = store && !pending.size;
      $("savedNote").textContent = saved ? "Your answers are saved to this page. Tell whoever shared it that you're done." : "";
      $("exportBox").hidden = saved;
      if (!saved) $("exportText").value = exportCode();
      return;
    }
    $("judge").hidden = false; $("done").hidden = true;
    const p = PAIRS[idx];
    $("n").textContent = idx + 1;
    $("imgA").src = IMG[p.a]; $("imgB").src = IMG[p.b];
    $("back").disabled = !ready || idx === 0;
    paintQuestions();
    shownAt = performance.now();
  }

  async function markRoot() {                       // one parent doc so Claude can list who rated
    if (rootMarked || !store) return;
    rootMarked = true;
    try { await once(() => db.doc("ratings/" + uid).set({ started: new Date().toISOString() })); } catch (e) { rootMarked = false; }
  }
  async function save(rec) {
    try {
      await once(() => db.doc("ratings/" + uid + "/picks/" + rec.pair).set(rec));
      pending.delete(rec.pair);
      setStatus(pending.size ? "Saved. Earlier answers still waiting: " + pending.size + "." : "Saved.");
      markRoot();
      for (const r of [...pending.values()]) {
        try { await once(() => db.doc("ratings/" + uid + "/picks/" + r.pair).set(r)); pending.delete(r.pair); } catch (e) { break; }
      }
    } catch (e) {
      pending.set(rec.pair, rec);
      setStatus("Couldn't save pair " + rec.pair + " (" + ((e && e.code) || "error") + "). It's kept on this page and you'll get a code to send at the end.", true);
    }
  }

  function choosePref(v) {
    if (!ready || busy || idx < 0) return;
    pref = v; paintQuestions();
  }
  function chooseGuess(v) {
    if (!ready || busy || idx < 0 || !pref) return;
    busy = true;
    const p = PAIRS[idx];
    const rec = { pair: p.id, a: p.a, b: p.b, pref: pref, guess: v,
                  ms: Math.round(performance.now() - shownAt), at: new Date().toISOString(), v: 1 };
    picks[p.id] = rec; lsSave(); pref = null;
    if (store) save(rec);
    paintQuestions();
    setTimeout(function () { idx = nextOpen(idx); busy = false; render(); }, reduced ? 0 : 200);
  }
  function back() {
    if (!ready || busy) return;
    pref = null;
    if (idx < 0) idx = TOTAL - 1; else if (idx > 0) idx -= 1; else return;
    render();
  }

  $("cardA").addEventListener("click", function () { pref ? chooseGuess("a") : choosePref("a"); });
  $("cardB").addEventListener("click", function () { pref ? chooseGuess("b") : choosePref("b"); });
  $("p_a").addEventListener("click", function () { choosePref("a"); });
  $("p_b").addEventListener("click", function () { choosePref("b"); });
  $("p_tie").addEventListener("click", function () { choosePref("tie"); });
  $("g_a").addEventListener("click", function () { chooseGuess("a"); });
  $("g_b").addEventListener("click", function () { chooseGuess("b"); });
  $("g_none").addEventListener("click", function () { chooseGuess("none"); });
  $("back").addEventListener("click", back);
  $("review").addEventListener("click", function () { idx = TOTAL - 1; pref = null; render(); });
  $("copy").addEventListener("click", function () {
    const t = $("exportText");
    const fallback = function () { t.focus(); t.select(); $("copyMsg").textContent = "Selected. Press Ctrl+C or Cmd+C to copy."; };
    try { navigator.clipboard.writeText(t.value).then(function () { $("copyMsg").textContent = "Copied."; }, fallback); }
    catch (e) { fallback(); }
  });
  document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey || e.repeat || idx < 0) return;
    const k = e.key.toLowerCase();
    const map = { "1": "a", "2": "b", "3": null };
    if (k in map) {
      e.preventDefault();
      if (!pref) choosePref(k === "3" ? "tie" : map[k]); else chooseGuess(k === "3" ? "none" : map[k]);
    } else if (k === "u" || k === "backspace") { e.preventDefault(); back(); }
  });

  async function init() {
    render(); setStatus("Loading…");
    const local = lsLoad();
    try {
      const [d, u] = await Promise.all([window.claude && window.claude.use ? window.claude.use("db") : null,
                                        window.claude && window.claude.use ? window.claude.use("user") : null]);
      db = d; uid = u ? await u.id() : null;
    } catch (e) { db = null; uid = null; }
    if (db && uid) {
      try {
        const snap = await once(() => db.collection("ratings/" + uid + "/picks").get());
        for (const doc of snap.docs) { const v = doc.data(); if (v && typeof v.pair === "string") picks[v.pair] = v; }
        store = true;
        for (const id of Object.keys(local)) {
          if (!picks[id] && PAIRS.some(function (p) { return p.id === id; })) { picks[id] = local[id]; pending.set(id, local[id]); }
        }
        const n = doneCount();
        setStatus(n ? "Picked up where you left off: " + n + " of " + TOTAL + " done." : "");
      } catch (e) {
        picks = local; store = false;
        setStatus("Answers are kept in this browser; you'll get a code to send at the end.", false);
      }
    } else {
      picks = local;
      setStatus("Answers are kept in this browser; you'll get a code to send at the end.", false);
    }
    idx = nextOpen(-1); ready = true; render();
    if (store && pending.size) { const r = pending.values().next().value; save(r); }
  }
  init();
})();
</script>
'''

if __name__ == "__main__":
    main()

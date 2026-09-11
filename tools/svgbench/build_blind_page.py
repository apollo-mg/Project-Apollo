#!/usr/bin/env python3
"""Build the blind pairwise rating page for the svgbench ladder drawings.

The page carries NO model, quant, rep or step labels: each render gets a random code, and the only
map from code to drawing is MAPPING_SEALED.json. It stays out of git until rating is done; its
SHA-256 is committed in PREREG_BLIND_ART.md first, so it cannot change unnoticed. Pairs, sides and
order are shuffled once, from the OS RNG, on the first build. Later builds reuse the sealed mapping,
so the page can be regenerated without reshuffling. To reshuffle, delete the mapping deliberately --
which voids the prereg.

Renders are composited onto white, as svg_probe scores them, and re-encoded so no source metadata
(file names included) can ride along into the page.

Usage: build_blind_page.py OUT.html
"""
import base64, hashlib, io, itertools, json, random, re, sys, datetime
from pathlib import Path
from PIL import Image

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
SRC = ROOT / "data/receipts/svgbench-ladder"
MAPPING = ROOT / "data/receipts/svgbench-blind/MAPPING_SEALED.json"
ALPHABET = "ACDEFHJKLMNPRTUVWXY3479"   # no 0/O, 1/I, 2/Z, 5/S, 6/G, 8/B lookalikes
N_REPEATS, MIN_GAP, REPEAT_POOL = 8, 12, 45
PARENT = {"intent2": "p1", "goal2": "p1", "goal3": "goal2"}
QUESTION = "Which is the better picture of a pelican riding a bicycle?"
NAME = re.compile(r"^(UD-.+)_r(\d)_(p1|intent2|goal2|goal3)\.png$")


def make_mapping():
    rng = random.SystemRandom()
    draw, used = {}, set()
    for f in sorted(SRC.glob("UD-*.png")):
        m = NAME.match(f.name)
        if not m:
            continue
        code = "".join(rng.choice(ALPHABET) for _ in range(4))
        while code in used:
            code = "".join(rng.choice(ALPHABET) for _ in range(4))
        used.add(code)
        draw[code] = {"quant": m[1], "rep": int(m[2]), "step": m[3], "png": f.name}
    key = {(v["quant"], v["rep"], v["step"]): c for c, v in draw.items()}

    base = [{"kind": "first", "pair": list(xy)}
            for xy in itertools.combinations(sorted(c for c, v in draw.items() if v["step"] == "p1"), 2)]
    for c, v in draw.items():
        if v["step"] in PARENT:
            parent = key[(v["quant"], v["rep"], PARENT[v["step"]])]
            base.append({"kind": "revision", "pair": [parent, c], "parent": parent, "child": c,
                         "framing": "intent" if v["step"] == "intent2" else "goal"})
    for b in base:
        rng.shuffle(b["pair"])                     # which side each drawing sits on
    rng.shuffle(base)                              # presentation order

    order = list(base)
    for pos in sorted(rng.sample(range(REPEAT_POOL), N_REPEATS)):
        src = base[pos]
        cur = next(i for i, o in enumerate(order) if o is src)
        order.insert(rng.randint(cur + MIN_GAP + 1, len(order)),
                     {"kind": "repeat", "pair": src["pair"][::-1], "_src": src})
    for i, p in enumerate(order, 1):
        p["id"] = f"q{i:03d}"
    for p in order:
        if p["kind"] == "repeat":
            p["repeat_of"] = p.pop("_src")["id"]
    return {"built_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "question": QUESTION, "min_gap": MIN_GAP, "drawings": draw,
            "pairs": [{k: v for k, v in p.items()} for p in order]}


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
        MAPPING.parent.mkdir(parents=True, exist_ok=True)
        MAPPING.write_text(json.dumps(mp, indent=1, sort_keys=True) + "\n")
        print(f"NEW mapping written: {MAPPING}")
    page = {"pairs": [{"id": p["id"], "a": p["pair"][0], "b": p["pair"][1]} for p in mp["pairs"]],
            "img": {c: data_uri(SRC / v["png"]) for c, v in mp["drawings"].items()}}
    out.write_text(TEMPLATE.replace("/*DATA*/null", json.dumps(page, separators=(",", ":"))))
    kinds = {}
    for p in mp["pairs"]:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print(f"drawings {len(mp['drawings'])}  pairs {len(mp['pairs'])} {kinds}")
    print(f"page {out} ({out.stat().st_size / 1e6:.2f} MB)")
    print(f"MAPPING_SEALED.json sha256 {hashlib.sha256(MAPPING.read_bytes()).hexdigest()}")


TEMPLATE = r'''<title>Blind Pelican Judging</title>
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
.judge{display:grid;gap:16px}
.question{margin:0;font-size:clamp(1.1rem,2.2vw,1.35rem);font-weight:600;line-height:1.3;text-wrap:balance}
.question small{display:block;margin-top:4px;font-size:0.9rem;font-weight:400;color:var(--ink-2)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:clamp(12px,2.5vw,28px)}
@media (max-width:520px){
  .wrap{gap:12px}
  .pair{grid-template-columns:1fr;gap:10px}
  .frame{padding:6px}
  .frame img{width:auto;height:auto;max-height:30vh;margin-inline:auto}   /* both drawings on one phone screen */
}
.card{appearance:none;border:0;margin:0;padding:0;background:none;color:inherit;font:inherit;text-align:left;cursor:pointer;display:grid;gap:8px}
.frame{display:block;background:var(--paper);border:1px solid var(--rule);border-radius:3px;padding:10px;transition:border-color .12s,box-shadow .12s,background-color .12s}
.frame img{display:block;width:100%;max-width:100%;height:auto;aspect-ratio:4/3;border:1px solid var(--rule)}
.tag{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding-inline:2px;font-family:var(--type);font-size:0.9rem;color:var(--ink-2)}
.code{color:var(--ink);font-weight:700;letter-spacing:0.08em}
.card:hover:not([disabled]) .frame{border-color:var(--pouch)}
.card:focus-visible{outline:none}
.card:focus-visible .frame{box-shadow:0 0 0 3px var(--sea)}
.card.chosen .frame{border-color:var(--pouch);background:var(--pouch-soft);box-shadow:0 0 0 2px var(--pouch)}
.card[disabled]{cursor:progress}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px 20px}
.btn{font:600 0.95rem/1 var(--sans);padding:11px 16px;border-radius:3px;border:1px solid var(--ink-2);background:transparent;color:var(--ink);cursor:pointer}
.btn:hover:not([disabled]){border-color:var(--ink)}
.btn.chosen{background:var(--pouch);border-color:var(--pouch);color:var(--on-pouch)}
.btn[disabled]{opacity:.45;cursor:progress}
.toggle{display:inline-flex;align-items:center;gap:8px;font-size:0.95rem;cursor:pointer}
.toggle input{width:18px;height:18px;margin:0;accent-color:var(--pouch)}
.link{font:inherit;font-size:0.95rem;padding:0;border:0;background:none;color:var(--ink-2);text-decoration:underline;text-underline-offset:3px;cursor:pointer}
.link[disabled]{opacity:.4;cursor:default}
.btn:focus-visible,.link:focus-visible,.toggle input:focus-visible{outline:3px solid var(--sea);outline-offset:2px}
.prevpick{font-family:var(--type);font-size:0.9rem;color:var(--ink-2)}
.keys{margin:0;font-family:var(--type);font-size:0.85rem;color:var(--ink-2)}
@media (hover:none){.keys{display:none}}
.status{min-height:1.5em;font-size:0.9rem;color:var(--ink-2)}
.status.warn{color:var(--ink);font-weight:600}
.done{display:grid;gap:10px;padding:24px;background:var(--paper);border:1px solid var(--rule);border-radius:3px}
.done h2{margin:0;font-size:1.3rem;text-wrap:balance}
.done p{margin:0;max-width:62ch}
footer{padding-block:12px 0;border-top:1px solid var(--rule);font-size:0.85rem;color:var(--ink-2)}
footer p{margin:0;max-width:72ch}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>

<div class="wrap">
  <header>
    <h1>Blind Pelican Judging</h1>
    <div class="count">Pair <b id="n">1</b> of <span id="total">75</span> &middot; <span id="judged">0</span> judged</div>
  </header>
  <div class="progress" aria-hidden="true"><i id="bar"></i></div>

  <main class="judge" id="judge">
    <p class="question">Which is the better picture of a pelican riding a bicycle?
      <small>Judge each picture as a whole. Every drawing answered the same prompt, and no labels are shown.</small></p>
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
      <label class="toggle" for="seen"><input type="checkbox" id="seen"><span>I've seen one of these before</span></label>
      <button class="link" id="back" type="button">Back one pair</button>
      <span class="prevpick" id="prev"></span>
    </div>
    <p class="keys">Keys: 1 or &larr; picks A &middot; 2 or &rarr; picks B &middot; T too close &middot; S seen before &middot; U back</p>
    <div class="status" id="status" role="status" aria-live="polite"></div>
  </main>

  <section class="done" id="done" hidden>
    <h2>All pairs judged.</h2>
    <p id="doneText"></p>
    <p>Tell Claude you're done. Codes are matched to models in the analysis, never on this page.</p>
    <p><button class="link" id="review" type="button">Go back and change a pick</button></p>
  </section>

  <footer><p>Each drawing is the 512&times;384 render the svgbench scorer saw, composited onto white and tagged with a random code. The page holds no model or quant labels. Pairs, sides and order were shuffled once when the page was built, and some pairs come round twice.</p></footer>
</div>

<script>
(function () {
  const DATA = /*DATA*/null;
  const PAIRS = DATA.pairs, IMG = DATA.img, TOTAL = PAIRS.length;
  const $ = (id) => document.getElementById(id);
  const reduced = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const LS_KEY = "blind-pelican-picks-v1";
  const LOCAL_NOTE = "Saving in this browser only, so Claude can't read these picks. Open the page on claude.ai to save them where Claude can.";
  let picks = {}, idx = 0, shownAt = 0, store = null, ready = false, busy = false, flushing = false;
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
  function setEnabled(on) {
    for (const id of ["cardA", "cardB", "tie", "seen"]) $(id).disabled = !on;
    $("back").disabled = !on || idx === 0;
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function once(fn) {           // one retry after a short randomized delay, for transient faults only
    try { return await fn(); }
    catch (e) { if (e && e.code === "unavailable") { await sleep(400 + Math.random() * 500); return fn(); } throw e; }
  }

  function render() {
    const n = doneCount();
    $("bar").style.width = (100 * n / TOTAL).toFixed(1) + "%";
    $("judged").textContent = n;
    $("total").textContent = TOTAL;
    if (idx < 0) {
      $("judge").hidden = true; $("done").hidden = false;
      let ties = 0, seen = 0;
      for (const p of PAIRS) { const r = picks[p.id]; if (!r) continue; if (r.choice === "tie") ties++; if (r.seen) seen++; }
      $("n").textContent = TOTAL;
      $("doneText").textContent = ties + " called too close to call, " + seen + " flagged as seen before.";
      return;
    }
    $("judge").hidden = false; $("done").hidden = true;
    const p = PAIRS[idx], prev = picks[p.id];
    $("n").textContent = idx + 1;
    $("imgA").src = IMG[p.a]; $("imgB").src = IMG[p.b];
    $("codeA").textContent = p.a; $("codeB").textContent = p.b;
    $("cardA").classList.toggle("chosen", !!prev && prev.choice === "a");
    $("cardB").classList.toggle("chosen", !!prev && prev.choice === "b");
    $("tie").classList.toggle("chosen", !!prev && prev.choice === "tie");
    $("seen").checked = !!(prev && prev.seen);
    $("back").disabled = !ready || idx === 0;
    $("prev").textContent = !prev ? "" : prev.choice === "tie" ? "Your pick: too close to call" : "Your pick: " + prev.choice.toUpperCase();
    shownAt = performance.now();
  }

  async function retryPending() {
    if (flushing || !store || !pending.size) return;
    flushing = true;
    for (const rec of [...pending.values()]) {
      try { await once(() => store.doc("picks/" + rec.pair).set(rec)); pending.delete(rec.pair); }
      catch (e) { break; }
    }
    flushing = false;
    if (!pending.size) setStatus("Saved.");
  }
  async function save(rec) {
    try {
      await once(() => store.doc("picks/" + rec.pair).set(rec));
      pending.delete(rec.pair);
      setStatus(pending.size ? "Saved. Earlier picks still waiting to save: " + pending.size + "." : "Saved.");
      retryPending();
    } catch (e) {
      pending.set(rec.pair, rec);
      setStatus("Couldn't save pair " + rec.pair + " (" + ((e && e.code) || "error") + "). It's kept on this page and retries after your next pick saves.", true);
    }
  }

  function choose(choice) {
    if (!ready || busy || idx < 0) return;
    busy = true;
    const p = PAIRS[idx];
    const rec = { pair: p.id, a: p.a, b: p.b, choice: choice, seen: $("seen").checked,
                  ms: Math.round(performance.now() - shownAt), at: new Date().toISOString(), v: 1 };
    picks[p.id] = rec; lsSave();
    $("cardA").classList.toggle("chosen", choice === "a");
    $("cardB").classList.toggle("chosen", choice === "b");
    $("tie").classList.toggle("chosen", choice === "tie");
    if (store) save(rec);
    setTimeout(function () { idx = nextOpen(idx); busy = false; render(); }, reduced ? 0 : 180);
  }
  function back() {
    if (!ready || busy) return;
    if (idx < 0) idx = TOTAL - 1; else if (idx > 0) idx -= 1; else return;
    render();
  }

  $("cardA").addEventListener("click", function () { choose("a"); });
  $("cardB").addEventListener("click", function () { choose("b"); });
  $("tie").addEventListener("click", function () { choose("tie"); });
  $("back").addEventListener("click", back);
  $("review").addEventListener("click", function () { idx = TOTAL - 1; render(); });
  document.addEventListener("keydown", function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return;
    const k = e.key.toLowerCase();
    if (k === "1" || k === "arrowleft") { e.preventDefault(); choose("a"); }
    else if (k === "2" || k === "arrowright") { e.preventDefault(); choose("b"); }
    else if (k === "t" || k === "3") { e.preventDefault(); choose("tie"); }
    else if (k === "s") { e.preventDefault(); if (!$("seen").disabled) $("seen").checked = !$("seen").checked; }
    else if (k === "u" || k === "backspace") { e.preventDefault(); back(); }
  });

  async function init() {
    setEnabled(false); render(); setStatus("Loading saved picks…");
    let db = null;
    try { if (window.claude && typeof window.claude.use === "function") db = await window.claude.use("db"); } catch (e) { db = null; }
    const local = lsLoad();
    if (db) {
      try {
        const snap = await once(() => db.collection("picks").get());
        for (const d of snap.docs) { const v = d.data(); if (v && typeof v.pair === "string") picks[v.pair] = v; }
        store = db;
        for (const id of Object.keys(local)) {       // picks made where storage wasn't reachable
          if (!picks[id] && PAIRS.some(function (p) { return p.id === id; })) { picks[id] = local[id]; pending.set(id, local[id]); }
        }
        const n = doneCount();
        setStatus(n ? "Picked up where you left off: " + n + " of " + TOTAL + " judged." : "");
        retryPending();
      } catch (e) {
        picks = local; store = null;
        setStatus("Saved picks couldn't be loaded (" + ((e && e.code) || "error") + "). " + LOCAL_NOTE, true);
      }
    } else {
      picks = local;
      setStatus(LOCAL_NOTE, true);
    }
    idx = nextOpen(-1); ready = true; setEnabled(true); render();
  }
  init();
})();
</script>
'''

if __name__ == "__main__":
    main()

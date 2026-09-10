# buun fork: DFlash loads, announces itself, and drafts nothing

**2026-08-26.** 9070 XT (gfx1201). buun-llama-cpp **`2714303`**, `build_rocm`.
Control: TheTom/llama-cpp-turboquant **`f97400563`** — same GPU, same model, same projection
file, **works**.

## Two separate problems, one blocking and one silent

### A. Dynamic VBR blocks all draft-model speculation, and VBR is default-on

With no `-ct` flag at all, the VBR controller arms itself:

```
I VBR dynamic runtime controller: KV budget auto (remaining VRAM, resolved by fit) ...
  decode-time degrade controller armed
```

Then any draft model fails:

```
E llama_init_from_model: failed to initialize the context: multiple independent dynamic-VBR
  contexts in one process are unsupported: the co-tenancy ledger has one marker identity
  per process
E srv load_model: failed to create shared DFlash drafter context
```

Source: `src/llama-context.cpp:670`, guarded by
`memory->vbr_ledger_tree_active() && llama_vram_ledger_armed()`.

MTP is unaffected — its head is embedded (`blk.32`) and shares the target's context. Only
**dual-context** speculation (DFlash, and presumably DFlash2/eagle3/draft-simple) trips it.

**Workaround, verified:** `-ctk f16 -ctv f16`. With VBR off the ledger is not armed and the
drafter initialises.

**Why it matters:** a user who never asked for VBR loses draft-model speculation and gets an
error that names VBR. On RDNA4 that means losing the *faster* option — DFlash n=8 reaches
1.77x baseline on code where MTP n=2 reaches 1.48x.

### B. With VBR off it loads — and still drafts nothing

This is the worse one, because it is silent.

```
I load_model: auto-detected DFlash drafter (block_size=16)
I load_model: DFlash enabled for all 1 slots
I common_speculative_init: adding implementation dflash
dflash gpu ring: allocated 0 layers x 512 slots x 4096 embd + staging (~0 MB)
dflash: block_size=16, mask_token=0, n_target_layers=0, n_embd=4096, target_ids=[]
```

**`0 layers`, `n_target_layers=0`, `target_ids=[]`, ~0 MB staging.** It reports success at
every step, allocates nothing, and never drafts. Measured cost of that:

| arm | prose | code |
|---|---:|---:|
| baseline | 63.40 | 63.39 |
| DFlash n=2 | 58.66 | 57.47 |
| DFlash n=8 | 57.00 | 50.38 |
| DFlash n=15 | 54.88 | 55.41 |

Consistently **slower than not speculating**, with **no acceptance telemetry at any depth** —
which is the tell. A drafter that is working logs acceptance.

## The control: identical inputs, Tom's fork

Same GPU, same target GGUF, same projection GGUF, same flags:

| arm | prose | code | acceptance |
|---|---:|---:|---|
| DFlash n=2 | 78.10 | 98.14 | 0.500 / 0.734 |
| DFlash n=8 | 75.30 | **110.08** | 0.198 / 0.336 |

So the projection file is fine and the hardware is fine. Whatever populates target layers
resolves to zero in `2714303`.

## Suggested fix, in priority order

1. **Fail loudly.** `n_target_layers=0` / `target_ids=[]` should be an error, not an INFO
   line. Silent no-op costs ~10% and reads as "DFlash is slow on this hardware."
2. Reconsider whether the co-tenancy ledger needs to bar draft contexts, or whether the draft
   context can be excluded from the ledger.
3. If VBR must bar them, say so at argument-parse time rather than after model load.

## Reproduce

```bash
# buun 2714303, RDNA4 — silent no-op
llama-server -m Ornith-1.5-9B-AD-Q8_0-Q6_K.gguf \
  -md ornith1.5-9b-dflash-bf16-projection-Q4_K_M.gguf \
  -ngl 99 -c 8192 -np 1 --jinja -ctk f16 -ctv f16 --spec-type draft-dflash
# without -ctk/-ctv f16: hard failure on the co-tenancy ledger
```
